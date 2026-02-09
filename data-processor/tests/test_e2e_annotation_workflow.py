"""
End-to-end tests for annotation workflows.

Tests complete document processing pipelines from upload to export.
"""

import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

# Import test subjects
from storage.in_memory import store, Document, Annotation, Template, OcrStatus, LabelType, BoundingBox

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


class AnnotationWorkflowE2ETest(APITestCase):
    """End-to-end tests for complete annotation workflows."""

    def setUp(self):
        """Set up test data."""
        self.channel_id = "test-channel-123"
        self.user_id = "test-user-456"
        self.test_image_data = self._create_test_image_bytes()

    def _create_test_image_bytes(self):
        """Create test PNG image bytes."""
        from PIL import Image
        import io

        # Create a 400x500 invoice-like image
        img = Image.new('RGB', (400, 500), color='white')

        # Add some text-like features (simulate invoice layout)
        # Header area
        header_box = (20, 20, 360, 60)
        img.paste(Image.new('RGB', (340, 40), color=(240, 240, 240)), header_box)

        # Table area
        table_box = (20, 100, 360, 300)
        img.paste(Image.new('RGB', (340, 200), color=(250, 250, 250)), table_box)

        # Amount area
        amount_box = (250, 400, 130, 40)
        img.paste(Image.new('RGB', (110, 20), color=(240, 250, 240)), amount_box)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    @patch('api.views.OCR_AVAILABLE', True)
    @patch('api.views.TEMPLATE_MATCHING_AVAILABLE', True)
    def test_complete_invoice_processing_workflow(self):
        """Test complete workflow: upload -> annotate -> create template -> apply template -> OCR -> export."""
        # Step 1: Upload document
        upload_url = reverse('document-list-create')
        upload_data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.user_id,
        }
        upload_files = {
            'image': ('invoice_001.png', BytesIO(self.test_image_data), 'image/png')
        }

        upload_response = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        document_id = upload_response.data['id']

        # Step 2: Create manual annotations
        annotation_url = reverse('annotation-list-create', kwargs={'document_id': document_id})

        annotations_data = [
            {
                'label_type': 'header',
                'label_name': 'Invoice Number',
                'color': '#FF0000',
                'bounding_box': {
                    'x': 50,
                    'y': 30,
                    'width': 120,
                    'height': 25,
                    'rotation': 0
                }
            },
            {
                'label_type': 'amount',
                'label_name': 'Total Amount',
                'color': '#00FF00',
                'bounding_box': {
                    'x': 280,
                    'y': 410,
                    'width': 80,
                    'height': 20,
                    'rotation': 0
                }
            }
        ]

        created_annotations = []
        for ann_data in annotations_data:
            response = self.client.post(annotation_url, ann_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_annotations.append(response.data)

        # Step 3: Create template from annotated document
        template_url = reverse('template-list-create')
        template_data = {
            'channel_id': self.channel_id,
            'name': 'Invoice Template',
            'description': 'Standard invoice processing template',
            'source_document_id': document_id,
            'labels': [
                {
                    'label_type': 'header',
                    'label_name': 'Invoice Number',
                    'color': '#FF0000',
                    'relative_x': 50/400,  # Convert to relative coordinates
                    'relative_y': 30/500,
                    'relative_width': 120/400,
                    'relative_height': 25/500
                },
                {
                    'label_type': 'amount',
                    'label_name': 'Total Amount',
                    'color': '#00FF00',
                    'relative_x': 280/400,
                    'relative_y': 410/500,
                    'relative_width': 80/400,
                    'relative_height': 20/500
                }
            ]
        }

        template_response = self.client.post(template_url, template_data, format='json')
        self.assertEqual(template_response.status_code, status.HTTP_201_CREATED)
        template_id = template_response.data['id']

        # Step 4: Upload second document
        upload_data2 = {
            'channel_id': self.channel_id,
            'uploaded_by': self.user_id,
        }
        upload_files2 = {
            'image': ('invoice_002.png', BytesIO(self.test_image_data), 'image/png')
        }

        upload_response2 = self.client.post(upload_url, upload_data2, files=upload_files2, format='multipart')
        self.assertEqual(upload_response2.status_code, status.HTTP_201_CREATED)
        document_id2 = upload_response2.data['id']

        # Step 5: Apply template to second document
        apply_url = reverse('template-apply', kwargs={'document_id': document_id2})
        apply_data = {
            'template_id': template_id,
            'use_feature_matching': False  # Use relative positioning for test
        }

        apply_response = self.client.post(apply_url, apply_data, format='json')
        self.assertEqual(apply_response.status_code, status.HTTP_200_OK)
        self.assertEqual(apply_response.data['annotations_created'], 2)
        self.assertEqual(apply_response.data['template_id'], template_id)

        # Step 6: Run OCR processing on second document
        with patch('api.views.process_document') as mock_process:
            # Mock OCR result
            mock_ocr_result = MagicMock()
            mock_ocr_result.to_dict.return_value = {
                'full_text': 'INVOICE #002\nTotal: $456.78',
                'word_count': 4,
                'average_confidence': 0.92,
                'detected_regions': []
            }
            mock_ocr_result.full_text = 'INVOICE #002\nTotal: $456.78'
            mock_ocr_result.word_count = 4
            mock_ocr_result.average_confidence = 0.92
            mock_ocr_result.detected_regions = []

            mock_process.return_value = (mock_ocr_result, {'original_size': (400, 500)})

            ocr_url = reverse('document-process', kwargs={'document_id': document_id2})
            ocr_response = self.client.post(ocr_url, {}, format='json')

            self.assertEqual(ocr_response.status_code, status.HTTP_200_OK)
            self.assertEqual(ocr_response.data['status'], 'completed')
            self.assertEqual(ocr_response.data['word_count'], 4)

        # Step 7: Extract text for annotations
        with patch('api.views.extract_text_for_annotations') as mock_extract:
            # Mock extracted text results
            mock_annotations = []
            for i, ann in enumerate(created_annotations):
                mock_ann = MagicMock()
                mock_ann.id = ann['id']
                mock_ann.extracted_text = 'INV-002' if i == 0 else '$456.78'
                mock_ann.confidence = 0.95 if i == 0 else 0.88
                mock_annotations.append(mock_ann)

            mock_extract.return_value = mock_annotations

            extract_url = reverse('annotation-extract-text', kwargs={'document_id': document_id2})
            extract_response = self.client.post(extract_url, {}, format='json')

            self.assertEqual(extract_response.status_code, status.HTTP_200_OK)
            self.assertEqual(extract_response.data['annotations_updated'], 2)

        # Step 8: Export processed data
        export_url = reverse('document-export', kwargs={'document_id': document_id2})
        export_data = {'format': 'json'}

        export_response = self.client.post(export_url, export_data, format='json')
        self.assertEqual(export_response.status_code, status.HTTP_200_OK)

        # Verify export contains expected data
        exported_data = export_response.data
        self.assertEqual(exported_data['document_id'], document_id2)
        self.assertEqual(len(exported_data['fields']), 2)

        # Check that fields have extracted text
        fields = exported_data['fields']
        invoice_field = next(f for f in fields if f['name'] == 'Invoice Number')
        amount_field = next(f for f in fields if f['name'] == 'Total Amount')

        self.assertEqual(invoice_field['type'], 'header')
        self.assertEqual(amount_field['type'], 'amount')
        self.assertIsNotNone(invoice_field['value'])
        self.assertIsNotNone(amount_field['value'])

    def test_batch_processing_workflow(self):
        """Test batch processing of multiple documents."""
        # Upload multiple documents
        document_ids = []
        for i in range(3):
            upload_url = reverse('document-list-create')
            upload_data = {
                'channel_id': self.channel_id,
                'uploaded_by': self.user_id,
            }
            upload_files = {
                'image': (f'doc_{i+1}.png', BytesIO(self.test_image_data), 'image/png')
            }

            response = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            document_ids.append(response.data['id'])

        # Create batch job
        batch_url = reverse('batch-job-list-create')
        batch_data = {
            'channel_id': self.channel_id,
            'created_by': self.user_id,
            'template_id': None,  # No template for this test
            'document_ids': document_ids
        }

        batch_response = self.client.post(batch_url, batch_data, format='json')
        self.assertEqual(batch_response.status_code, status.HTTP_201_CREATED)
        batch_job_id = batch_response.data['id']

        # Verify batch job was created
        self.assertEqual(len(batch_response.data['document_ids']), 3)
        self.assertEqual(batch_response.data['status'], 'pending')

        # Retrieve batch job details
        detail_url = reverse('batch-job-detail', kwargs={'batch_job_id': batch_job_id})
        detail_response = self.client.get(detail_url)

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['id'], batch_job_id)
        self.assertEqual(len(detail_response.data['document_ids']), 3)

    def test_template_reuse_workflow(self):
        """Test creating and reusing templates across multiple documents."""
        # Create template
        template_url = reverse('template-list-create')
        template_data = {
            'channel_id': self.channel_id,
            'name': 'Reusable Template',
            'description': 'Template for multiple document types',
            'labels': [
                {
                    'label_type': 'header',
                    'label_name': 'Document Title',
                    'color': '#FF0000',
                    'relative_x': 0.1,
                    'relative_y': 0.05,
                    'relative_width': 0.4,
                    'relative_height': 0.08
                }
            ]
        }

        template_response = self.client.post(template_url, template_data, format='json')
        self.assertEqual(template_response.status_code, status.HTTP_201_CREATED)
        template_id = template_response.data['id']

        # Upload and process multiple documents with the same template
        processed_docs = []
        for i in range(2):
            # Upload document
            upload_url = reverse('document-list-create')
            upload_data = {
                'channel_id': self.channel_id,
                'uploaded_by': self.user_id,
            }
            upload_files = {
                'image': (f'document_{i+1}.png', BytesIO(self.test_image_data), 'image/png')
            }

            upload_response = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
            self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
            doc_id = upload_response.data['id']

            # Apply template
            apply_url = reverse('template-apply', kwargs={'document_id': doc_id})
            apply_data = {
                'template_id': template_id,
                'use_feature_matching': False
            }

            apply_response = self.client.post(apply_url, apply_data, format='json')
            self.assertEqual(apply_response.status_code, status.HTTP_200_OK)
            self.assertEqual(apply_response.data['annotations_created'], 1)

            processed_docs.append(doc_id)

        # Verify both documents have the template applied
        for doc_id in processed_docs:
            doc_detail_url = reverse('document-detail', kwargs={'document_id': doc_id})
            doc_response = self.client.get(doc_detail_url)
            self.assertEqual(doc_response.status_code, status.HTTP_200_OK)
            self.assertEqual(doc_response.data['template_id'], template_id)

    def test_annotation_validation_workflow(self):
        """Test annotation validation and quality control workflow."""
        # Upload document
        upload_url = reverse('document-list-create')
        upload_data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.user_id,
        }
        upload_files = {
            'image': ('validation_test.png', BytesIO(self.test_image_data), 'image/png')
        }

        upload_response = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        document_id = upload_response.data['id']

        # Create annotations with different validation statuses
        annotation_url = reverse('annotation-list-create', kwargs={'document_id': document_id})

        annotations = [
            {
                'label_type': 'header',
                'label_name': 'Valid Header',
                'color': '#FF0000',
                'bounding_box': {'x': 50, 'y': 50, 'width': 100, 'height': 30, 'rotation': 0},
                'validation_status': 'valid'
            },
            {
                'label_type': 'amount',
                'label_name': 'Invalid Amount',
                'color': '#00FF00',
                'bounding_box': {'x': 200, 'y': 200, 'width': 80, 'height': 25, 'rotation': 0},
                'validation_status': 'invalid'
            },
            {
                'label_type': 'custom',
                'label_name': 'Pending Review',
                'color': '#0000FF',
                'bounding_box': {'x': 100, 'y': 300, 'width': 120, 'height': 35, 'rotation': 0},
                'validation_status': 'pending'
            }
        ]

        created_annotations = []
        for ann in annotations:
            response = self.client.post(annotation_url, ann, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_annotations.append(response.data)

        # Test exporting only validated annotations
        export_url = reverse('document-export', kwargs={'document_id': document_id})

        # Export all annotations
        export_all = self.client.post(export_url, {'format': 'json'}, format='json')
        self.assertEqual(export_all.status_code, status.HTTP_200_OK)
        self.assertEqual(len(export_all.data['fields']), 3)

        # Export only validated annotations
        export_validated = self.client.post(export_url, {
            'format': 'json',
            'validated_only': True
        }, format='json')
        self.assertEqual(export_validated.status_code, status.HTTP_200_OK)
        self.assertEqual(len(export_validated.data['fields']), 1)
        self.assertEqual(export_validated.data['fields'][0]['name'], 'Valid Header')

        # Update annotation validation status
        update_url = reverse('annotation-detail', kwargs={
            'document_id': document_id,
            'annotation_id': created_annotations[2]['id']  # Pending Review
        })

        update_response = self.client.put(update_url, {
            'validation_status': 'valid'
        }, format='json')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data['validation_status'], 'valid')

        # Re-export validated annotations
        export_validated_again = self.client.post(export_url, {
            'format': 'json',
            'validated_only': True
        }, format='json')
        self.assertEqual(export_validated_again.status_code, status.HTTP_200_OK)
        self.assertEqual(len(export_validated_again.data['fields']), 2)

    def test_error_handling_workflow(self):
        """Test error handling throughout the workflow."""
        # Test uploading invalid document
        upload_url = reverse('document-list-create')
        upload_data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.user_id,
        }
        # Missing image file
        response = self.client.post(upload_url, upload_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Upload valid document
        upload_files = {
            'image': ('test.png', BytesIO(self.test_image_data), 'image/png')
        }
        valid_upload = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
        self.assertEqual(valid_upload.status_code, status.HTTP_201_CREATED)
        document_id = valid_upload.data['id']

        # Test operations on non-existent document
        fake_doc_url = reverse('annotation-list-create', kwargs={'document_id': 'non-existent'})
        response = self.client.get(fake_doc_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Test applying non-existent template
        apply_url = reverse('template-apply', kwargs={'document_id': document_id})
        apply_data = {'template_id': 'fake-template-id'}
        response = self.client.post(apply_url, apply_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Test OCR processing on document without image data
        # (This would require mocking the document to have no image_data)
        ocr_url = reverse('document-process', kwargs={'document_id': document_id})
        with patch('api.views.OCR_AVAILABLE', False):
            response = self.client.post(ocr_url, {}, format='json')
            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_data_consistency_workflow(self):
        """Test data consistency across operations."""
        # Upload document
        upload_url = reverse('document-list-create')
        upload_data = {
            'channel_id': self.channel_id,
            'uploaded_by': self.user_id,
        }
        upload_files = {
            'image': ('consistency_test.png', BytesIO(self.test_image_data), 'image/png')
        }

        upload_response = self.client.post(upload_url, upload_data, files=upload_files, format='multipart')
        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        document_id = upload_response.data['id']

        # Create annotation
        annotation_url = reverse('annotation-list-create', kwargs={'document_id': document_id})
        ann_data = {
            'label_type': 'header',
            'label_name': 'Test Header',
            'color': '#FF0000',
            'bounding_box': {'x': 50, 'y': 50, 'width': 100, 'height': 30, 'rotation': 0}
        }

        ann_response = self.client.post(annotation_url, ann_data, format='json')
        self.assertEqual(ann_response.status_code, status.HTTP_201_CREATED)
        annotation_id = ann_response.data['id']

        # Verify annotation appears in document details
        doc_detail_url = reverse('document-detail', kwargs={'document_id': document_id})
        doc_response = self.client.get(doc_detail_url)
        self.assertEqual(doc_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(doc_response.data['annotations']), 1)
        self.assertEqual(doc_response.data['annotations'][0]['id'], annotation_id)

        # Verify annotation appears in annotation list
        ann_list_response = self.client.get(annotation_url)
        self.assertEqual(ann_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ann_list_response.data['count'], 1)
        self.assertEqual(ann_list_response.data['annotations'][0]['id'], annotation_id)

        # Delete annotation
        delete_url = reverse('annotation-detail', kwargs={
            'document_id': document_id,
            'annotation_id': annotation_id
        })
        delete_response = self.client.delete(delete_url)
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

        # Verify annotation is removed from document
        doc_response_after = self.client.get(doc_detail_url)
        self.assertEqual(doc_response_after.status_code, status.HTTP_200_OK)
        self.assertEqual(len(doc_response_after.data['annotations']), 0)