"""
Integration tests for data-processor API endpoints.

Tests document upload, processing, annotation, template application, and export workflows.
"""

import pytest
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

# Import test subjects
from storage.in_memory import store, Document, Annotation, Template, OcrStatus, LabelType, BoundingBox
from api.serializers import DocumentSerializer, AnnotationSerializer, TemplateSerializer
from middleware.jwt_auth import TESTING_HEADER_KEY, TESTING_HEADER_VALUE

# Mock OCR services for testing
try:
    from services.ocr_pipeline import OcrResult, DetectedRegion
    from services.template_matcher import MatchResult, TransformedBox
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OcrResult = MagicMock
    DetectedRegion = MagicMock
    MatchResult = MagicMock
    TransformedBox = MagicMock


class DocumentUploadIntegrationTest(APITestCase):
    """Integration tests for document upload and processing workflow."""

    def setUp(self):
        """Set up test data."""
        self.client.defaults[
            f"HTTP_{TESTING_HEADER_KEY.upper().replace('-', '_')}"
        ] = TESTING_HEADER_VALUE
        self.channel_id = "test-channel-123"
        self.uploaded_by = "test-user-456"

        # Create a simple test image
        self.test_image_data = self._create_test_image_bytes()

    def _create_test_image_bytes(self):
        """Create test PNG image bytes."""
        from PIL import Image
        import io

        # Create a simple 100x100 red image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_document_upload_success(self):
        """Test successful document upload."""
        url = reverse('document-list-create')

        # Create multipart form data
        data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.uploaded_by,
        }
        files = {
            'image': ('test_document.png', BytesIO(self.test_image_data), 'image/png')
        }

        response = self.client.post(url, data, files=files, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['channel_id'], self.channel_id)
        self.assertEqual(response.data['uploaded_by'], self.uploaded_by)
        self.assertEqual(response.data['original_filename'], 'test_document.png')
        self.assertEqual(response.data['ocr_status'], 'pending')

        # Verify document was stored
        document = store.get_document(response.data['id'])
        self.assertIsNotNone(document)
        self.assertEqual(document.channel_id, self.channel_id)

    def test_document_upload_pdf_success(self):
        """Test successful PDF document upload."""
        url = reverse('document-list-create')

        data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.uploaded_by,
            'image': SimpleUploadedFile(
                'test_document.pdf',
                b'%PDF-1.4 test',
                content_type='application/pdf'
            )
        }

        pdf_result = SimpleNamespace(
            page_count=1,
            image_bytes=self.test_image_data,
            width=100,
            height=100,
            text_layer=[{'page': 1, 'text': 'Invoice 001'}],
        )

        with patch('api.views.extract_pdf_first_page', return_value=pdf_result), \
             patch('api.views.PDF_EXTRACTION_AVAILABLE', True), \
             patch('api.views.upload_image_to_minio', return_value='http://example.com/preview.png'):
            response = self.client.post(url, data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['file_type'], 'pdf')
        self.assertEqual(response.data['page_count'], 1)
        self.assertEqual(response.data['pdf_text_layer'][0]['text'], 'Invoice 001')

        document = store.get_document(response.data['id'])
        self.assertIsNotNone(document)
        self.assertEqual(document.file_type, 'pdf')

    def test_document_upload_missing_image(self):
        """Test document upload fails without image."""
        url = reverse('document-list-create')

        data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.uploaded_by,
        }

        response = self.client.post(url, data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_document_list_by_channel(self):
        """Test listing documents filtered by channel."""
        # Create test documents
        doc1 = Document(
            channel_id=self.channel_id,
            uploaded_by=self.uploaded_by,
            original_filename="doc1.png",
            image_data=self.test_image_data
        )
        doc2 = Document(
            channel_id="other-channel",
            uploaded_by=self.uploaded_by,
            original_filename="doc2.png",
            image_data=self.test_image_data
        )

        store.create_document(doc1)
        store.create_document(doc2)

        url = reverse('document-list-create')
        response = self.client.get(url, {'channel_id': self.channel_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['documents']), 1)
        self.assertEqual(response.data['documents'][0]['channel_id'], self.channel_id)

    def test_document_detail_retrieval(self):
        """Test retrieving document details."""
        # Create test document
        document = Document(
            channel_id=self.channel_id,
            uploaded_by=self.uploaded_by,
            original_filename="test.png",
            image_data=self.test_image_data
        )
        document = store.create_document(document)

        url = reverse('document-detail', kwargs={'document_id': document.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], document.id)
        self.assertEqual(response.data['channel_id'], self.channel_id)

    def test_document_detail_not_found(self):
        """Test retrieving non-existent document."""
        url = reverse('document-detail', kwargs={'document_id': 'non-existent-id'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)


class AnnotationIntegrationTest(APITestCase):
    """Integration tests for annotation management."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        # Add testing header for authentication
        self.client.defaults[HTTP_TESTING_HEADER_KEY] = TESTING_HEADER_VALUE

        self.channel_id = "test-channel-123"
        self.test_image_data = self._create_test_image_bytes()

        # Create test document
        self.document = Document(
            channel_id=self.channel_id,
            uploaded_by="test-user",
            original_filename="test.png",
            image_data=self.test_image_data
        )
        self.document = store.create_document(self.document)

    def _create_test_image_bytes(self):
        """Create test PNG image bytes."""
        from PIL import Image
        import io

        img = Image.new('RGB', (200, 200), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_create_annotation(self):
        """Test creating an annotation."""
        url = reverse('annotation-list-create', kwargs={'document_id': self.document.id})

        data = {
            'label_type': 'header',
            'label_name': 'Invoice Number',
            'color': '#FF0000',
            'bounding_box': {
                'x': 50,
                'y': 50,
                'width': 100,
                'height': 30,
                'rotation': 0
            }
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['label_type'], 'header')
        self.assertEqual(response.data['label_name'], 'Invoice Number')

        # Verify annotation was added to document
        document = store.get_document(self.document.id)
        self.assertEqual(len(document.annotations), 1)
        self.assertEqual(document.annotations[0].label_name, 'Invoice Number')

    def test_list_annotations(self):
        """Test listing annotations for a document."""
        # Create test annotations
        bbox1 = BoundingBox(x=10, y=10, width=50, height=20)
        bbox2 = BoundingBox(x=100, y=100, width=80, height=30)

        ann1 = Annotation(label_type=LabelType.HEADER, label_name="Header", bounding_box=bbox1)
        ann2 = Annotation(label_type=LabelType.AMOUNT, label_name="Amount", bounding_box=bbox2)

        store.add_annotation(self.document.id, ann1)
        store.add_annotation(self.document.id, ann2)

        url = reverse('annotation-list-create', kwargs={'document_id': self.document.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['annotations']), 2)

    def test_update_annotation(self):
        """Test updating an annotation."""
        # Create test annotation
        bbox = BoundingBox(x=10, y=10, width=50, height=20)
        annotation = Annotation(label_type=LabelType.HEADER, label_name="Header", bounding_box=bbox)
        annotation = store.add_annotation(self.document.id, annotation)

        url = reverse('annotation-detail', kwargs={
            'document_id': self.document.id,
            'annotation_id': annotation.id
        })

        update_data = {
            'label_name': 'Updated Header',
            'color': '#00FF00'
        }

        response = self.client.put(url, update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['label_name'], 'Updated Header')
        self.assertEqual(response.data['color'], '#00FF00')

    def test_delete_annotation(self):
        """Test deleting an annotation."""
        # Create test annotation
        bbox = BoundingBox(x=10, y=10, width=50, height=20)
        annotation = Annotation(label_type=LabelType.HEADER, label_name="Header", bounding_box=bbox)
        annotation = store.add_annotation(self.document.id, annotation)

        url = reverse('annotation-detail', kwargs={
            'document_id': self.document.id,
            'annotation_id': annotation.id
        })

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify annotation was removed
        document = store.get_document(self.document.id)
        self.assertEqual(len(document.annotations), 0)


class TemplateIntegrationTest(APITestCase):
    """Integration tests for template management."""

    def setUp(self):
        """Set up test data."""
        self.client.defaults[
            f"HTTP_{TESTING_HEADER_KEY.upper().replace('-', '_')}"
        ] = TESTING_HEADER_VALUE
        self.channel_id = "test-channel-123"
        self.test_image_data = self._create_test_image_bytes()

        # Create test document
        self.document = Document(
            channel_id=self.channel_id,
            uploaded_by="test-user",
            original_filename="test.png",
            image_data=self.test_image_data
        )
        self.document = store.create_document(self.document)

    def _create_test_image_bytes(self):
        """Create test PNG image bytes."""
        from PIL import Image
        import io

        img = Image.new('RGB', (300, 300), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_create_template(self):
        """Test creating a template."""
        url = reverse('template-list-create')

        data = {
            'channel_id': self.channel_id,
            'name': 'Invoice Template',
            'description': 'Template for invoice processing',
            'source_document_id': self.document.id,
            'labels': [
                {
                    'label_type': 'header',
                    'label_name': 'Invoice Number',
                    'color': '#FF0000',
                    'relative_x': 0.1,
                    'relative_y': 0.1,
                    'relative_width': 0.3,
                    'relative_height': 0.05
                }
            ]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['name'], 'Invoice Template')
        self.assertEqual(len(response.data['labels']), 1)

    def test_list_templates(self):
        """Test listing templates."""
        # Create test templates
        template1 = Template(
            channel_id=self.channel_id,
            created_by="user1",
            name="Template 1",
            labels=[]
        )
        template2 = Template(
            channel_id="other-channel",
            created_by="user2",
            name="Template 2",
            labels=[]
        )

        store.create_template(template1)
        store.create_template(template2)

        url = reverse('template-list-create')
        response = self.client.get(url, {'channel_id': self.channel_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['templates'][0]['name'], 'Template 1')

    @patch('api.views.TEMPLATE_MATCHING_AVAILABLE', True)
    @patch('api.views.OCR_AVAILABLE', True)
    def test_apply_template_to_document(self, mock_ocr, mock_template):
        """Test applying a template to a document."""
        # Create test template
        template = Template(
            channel_id=self.channel_id,
            created_by="test-user",
            name="Test Template",
            labels=[
                {
                    'label_type': LabelType.HEADER,
                    'label_name': 'Test Field',
                    'color': '#FF0000',
                    'relative_x': 0.1,
                    'relative_y': 0.1,
                    'relative_width': 0.2,
                    'relative_height': 0.05
                }
            ]
        )
        template = store.create_template(template)

        url = reverse('template-apply', kwargs={'document_id': self.document.id})

        data = {
            'template_id': template.id,
            'use_feature_matching': False  # Use relative positioning for test
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['template_id'], template.id)
        self.assertEqual(response.data['annotations_created'], 1)
        self.assertFalse(response.data['used_feature_matching'])

        # Verify annotation was created
        document = store.get_document(self.document.id)
        self.assertEqual(len(document.annotations), 1)
        self.assertEqual(document.template_id, template.id)


class ExportIntegrationTest(APITestCase):
    """Integration tests for data export functionality."""

    def setUp(self):
        """Set up test data."""
        self.client.defaults[
            f"HTTP_{TESTING_HEADER_KEY.upper().replace('-', '_')}"
        ] = TESTING_HEADER_VALUE
        self.channel_id = "test-channel-123"
        self.test_image_data = self._create_test_image_bytes()

        # Create test document
        self.document = Document(

            channel_id=self.channel_id,
            uploaded_by="test-user",
            original_filename="test.png",
            image_data=self.test_image_data,
            raw_ocr_text="Sample OCR text"
        )
        self.document = store.create_document(self.document)

        # Add test annotations
        bbox1 = BoundingBox(x=50, y=50, width=100, height=30)
        bbox2 = BoundingBox(x=150, y=150, width=80, height=40)

        ann1 = Annotation(
            label_type=LabelType.HEADER,
            label_name="Invoice Number",
            bounding_box=bbox1,
            extracted_text="INV-001",
            confidence=0.95
        )
        ann2 = Annotation(
            label_type=LabelType.AMOUNT,
            label_name="Total Amount",
            bounding_box=bbox2,
            extracted_text="$123.45",
            confidence=0.88
        )

        store.add_annotation(self.document.id, ann1)
        store.add_annotation(self.document.id, ann2)

    def _create_test_image_bytes(self):
        """Create test PNG image bytes."""
        from PIL import Image
        import io

        img = Image.new('RGB', (300, 300), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_export_json_format(self):
        """Test exporting document data as JSON."""
        url = reverse('document-export', kwargs={'document_id': self.document.id})

        data = {'format': 'json'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['document_id'], self.document.id)
        self.assertEqual(response.data['source_filename'], 'test.png')
        self.assertEqual(len(response.data['fields']), 2)
        self.assertEqual(response.data['raw_ocr_text'], 'Sample OCR text')

        # Check field data
        fields = response.data['fields']
        invoice_field = next(f for f in fields if f['name'] == 'Invoice Number')
        amount_field = next(f for f in fields if f['name'] == 'Total Amount')

        self.assertEqual(invoice_field['value'], 'INV-001')
        self.assertEqual(invoice_field['confidence'], 0.95)
        self.assertEqual(amount_field['value'], '$123.45')
        self.assertEqual(amount_field['confidence'], 0.88)

    def test_export_csv_format(self):
        """Test exporting document data as CSV."""
        url = reverse('document-export', kwargs={'document_id': self.document.id})

        data = {'format': 'csv'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['format'], 'csv')
        self.assertIn('content', response.data)

        # Verify CSV content contains expected data
        csv_content = response.data['content']
        self.assertIn('document_id,source_filename,field_name', csv_content)
        self.assertIn('Invoice Number', csv_content)
        self.assertIn('Total Amount', csv_content)
        self.assertIn('INV-001', csv_content)
        self.assertIn('$123.45', csv_content)

    def test_export_sql_format(self):
        """Test exporting document data as SQL."""
        url = reverse('document-export', kwargs={'document_id': self.document.id})

        data = {'format': 'sql'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['format'], 'sql')
        self.assertIn('statements', response.data)
        self.assertIn('parameters', response.data)

        statements = response.data['statements']
        params_list = response.data['parameters']
        self.assertGreater(len(statements), 1)  # Should have CREATE and INSERT statements
        self.assertEqual(len(statements), len(params_list))

        # Check for CREATE TABLE statement
        create_stmt = statements[0]
        self.assertIn('CREATE TABLE', create_stmt)
        self.assertIn('extracted_fields', create_stmt)
        self.assertIsNone(params_list[0])

        # Check for INSERT statements
        insert_stmts = statements[1:]
        insert_params = params_list[1:]
        self.assertEqual(len(insert_stmts), 2)  # One for each annotation
        for i, stmt in enumerate(insert_stmts):
            self.assertIn('INSERT INTO', stmt)
            self.assertIn('?', stmt)
            # Check if document.id is in the parameters
            self.assertEqual(insert_params[i][0], self.document.id)

    def test_export_unsupported_format(self):
        """Test exporting with unsupported format."""
        url = reverse('document-export', kwargs={'document_id': self.document.id})

        data = {'format': 'xml'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Unsupported format', response.data['error'])

    def test_export_validated_only(self):
        """Test exporting only validated annotations."""
        # Update one annotation to be validated
        annotations = store.get_document(self.document.id).annotations
        store.update_annotation(self.document.id, annotations[0].id, {'validation_status': 'valid'})

        url = reverse('document-export', kwargs={'document_id': self.document.id})

        data = {'format': 'json', 'validated_only': True}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['fields']), 1)  # Only validated annotation


class HealthCheckIntegrationTest(APITestCase):
    """Integration tests for health check endpoint."""

    def setUp(self):
        self.client.defaults[
            f"HTTP_{TESTING_HEADER_KEY.upper().replace('-', '_')}"
        ] = TESTING_HEADER_VALUE

    def test_health_check(self):
        """Test health check endpoint."""
        url = reverse('health-check')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['service'], 'data-processor')
        self.assertIn('storage', response.data)
        self.assertIn('version', response.data)


class BatchJobIntegrationTest(APITestCase):
    """Integration tests for batch job management."""

    def setUp(self):
        """Set up test data."""
        self.client.defaults[
            f"HTTP_{TESTING_HEADER_KEY.upper().replace('-', '_')}"
        ] = TESTING_HEADER_VALUE
        self.channel_id = "test-channel-123"

    def test_create_batch_job(self):
        """Test creating a batch job."""
        url = reverse('batch-job-list-create')

        data = {
            'channel_id': self.channel_id,
            'created_by': 'test-user',
            'template_id': 'template-123',
            'document_ids': ['doc1', 'doc2', 'doc3']
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['channel_id'], self.channel_id)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(len(response.data['document_ids']), 3)

    def test_list_batch_jobs(self):
        """Test listing batch jobs."""
        # Create test batch jobs
        job1 = store.create_batch_job({
            'channel_id': self.channel_id,
            'created_by': 'user1',
            'document_ids': ['doc1']
        })
        job2 = store.create_batch_job({
            'channel_id': 'other-channel',
            'created_by': 'user2',
            'document_ids': ['doc2']
        })

        url = reverse('batch-job-list-create')
        response = self.client.get(url, {'channel_id': self.channel_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['batch_jobs'][0]['channel_id'], self.channel_id)

    def test_get_batch_job_detail(self):
        """Test retrieving batch job details."""
        job = store.create_batch_job({
            'channel_id': self.channel_id,
            'created_by': 'test-user',
            'document_ids': ['doc1', 'doc2']
        })

        url = reverse('batch-job-detail', kwargs={'batch_job_id': job.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], job.id)
        self.assertEqual(response.data['channel_id'], self.channel_id)
        self.assertEqual(len(response.data['document_ids']), 2)
