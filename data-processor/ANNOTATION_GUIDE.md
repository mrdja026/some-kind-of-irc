# Data Processor Channel - Annotation Tools User Guide

## Overview

The Data Processor Channel provides powerful document annotation and OCR extraction capabilities. This guide explains how to use the annotation tools effectively for document processing workflows.

## Getting Started

### Creating a Data Processor Channel

1. In the channel sidebar, click the "+" button to create a new channel
2. Check the "Data Processor Channel" checkbox
3. Give your channel a descriptive name (e.g., "#invoice-processing")
4. Click "Create"

### Uploading Documents

1. In a data processor channel, click the "Attach" button or drag and drop image files
2. Supported formats: PNG, JPG, JPEG, WebP
3. Maximum file size: 10MB
4. Images are automatically resized to 1024x1024 pixels for processing

## Annotation Tools

### Label Types

The system provides predefined label types for common document elements:

- **Header**: Document titles, headings, and mastheads
- **Table**: Tabular data and structured information
- **Signature**: Signature blocks and authorization areas
- **Date**: Date fields and timestamps
- **Amount**: Monetary values and financial figures
- **Custom**: Any other document elements

### Creating Annotations

1. **Select Label Type**: Choose from the toolbar buttons (Header, Table, Signature, etc.)
2. **Draw Bounding Box**:
   - Click and drag on the document to create a rectangular selection
   - The bounding box will appear with the selected label's color
3. **Adjust Position**: Click and drag the bounding box to reposition
4. **Resize**: Drag the corner handles to adjust the size
5. **Rotate**: Some bounding boxes support rotation for angled text

### Annotation Properties

Each annotation has the following properties:

- **Label Name**: Descriptive name for the field (e.g., "Invoice Number", "Total Amount")
- **Color**: Visual identifier (automatically assigned based on label type)
- **Bounding Box**: Coordinates defining the annotation area
- **Extracted Text**: OCR results (populated after processing)
- **Confidence Score**: OCR accuracy rating (0.0 to 1.0)
- **Validation Status**: Manual quality control flag

## OCR Processing

### Automatic Processing

1. Upload an image to trigger automatic OCR processing
2. The system applies preprocessing (noise reduction, deskew, binarization)
3. OCR extracts text from the entire document
4. Results are stored and can be viewed in document details

### Manual Text Extraction

1. Create annotations on areas of interest
2. Click "Extract Text" to run OCR on specific regions
3. Review extracted text and confidence scores
4. Manually correct any OCR errors if needed

## Template Management

### Creating Templates

Templates capture annotation layouts for reuse across similar documents:

1. **Annotate a Sample Document**: Create annotations on a representative document
2. **Save as Template**:
   - Click the "Save Template" button
   - Give it a descriptive name (e.g., "Standard Invoice Layout")
   - Add a description of when to use this template
3. **Set Label Properties**:
   - Define expected formats (optional regex patterns)
   - Mark required fields
   - Set validation rules

### Template Features

- **Version Control**: Templates maintain change history
- **Sharing**: Templates are channel-specific but can be shared with team members
- **Intelligent Matching**: Uses computer vision to adapt templates to similar documents
- **Fallback Positioning**: Falls back to relative positioning if feature matching fails

### Applying Templates

1. **Upload New Document**: Upload a document similar to your template
2. **Select Template**: Choose from available templates in the channel
3. **Auto-Apply**: The system attempts feature-based matching
4. **Review Results**: Check that annotations are correctly positioned
5. **Manual Adjustments**: Reposition any misaligned annotations

## Data Export

### Export Formats

The system supports multiple export formats for downstream processing:

#### JSON Export

```json
{
  "document_id": "uuid",
  "source_filename": "invoice_001.png",
  "processed_at": "2026-01-26T12:00:00Z",
  "template_id": "uuid or null",
  "fields": [
    {
      "name": "invoice_number",
      "type": "header",
      "value": "INV-2026-001",
      "confidence": 0.95,
      "bounding_box": { "x": 100, "y": 50, "width": 200, "height": 30 },
      "validation_status": "valid"
    }
  ],
  "raw_ocr_text": "Full document text...",
  "metadata": {
    "preprocessing_applied": ["noise_reduction", "deskew"],
    "deskew_angle": 2.3,
    "ocr_engine": "tesseract-5.3.0"
  }
}
```

#### CSV Export

- Flattened structure with document reference columns
- Suitable for spreadsheet applications
- Includes confidence scores and validation status

#### SQL Export

- Parameterized INSERT statements
- Compatible with common database systems
- Includes table creation scripts

### Export Options

- **Include Metadata**: Add preprocessing and OCR engine information
- **Validated Only**: Export only manually validated annotations
- **Batch Export**: Process multiple documents simultaneously

## Best Practices

### Document Preparation

1. **Image Quality**: Use high-resolution scans (300+ DPI) for best OCR results
2. **Orientation**: Ensure documents are right-side up before uploading
3. **Lighting**: Well-lit, shadow-free scans produce better results
4. **File Formats**: PNG preferred for lossless quality, JPEG acceptable for photos

### Annotation Strategy

1. **Consistent Labeling**: Use the same label names across similar documents
2. **Precise Boundaries**: Draw bounding boxes tightly around text areas
3. **Label Type Selection**: Choose appropriate types for better organization
4. **Validation**: Always review OCR results and mark validation status

### Template Creation

1. **Representative Samples**: Create templates from typical documents
2. **Multiple Variants**: Consider creating templates for different document layouts
3. **Regular Updates**: Update templates as document formats change
4. **Team Standards**: Establish naming conventions for labels and templates

### Quality Control

1. **Confidence Thresholds**: Review annotations with low confidence scores (< 0.8)
2. **Manual Validation**: Mark high-confidence extractions as validated
3. **Error Correction**: Update incorrect OCR results manually
4. **Feedback Loop**: Use validation data to improve future processing

## Troubleshooting

### Common Issues

#### Poor OCR Accuracy

- **Cause**: Low-quality scans, unusual fonts, complex layouts
- **Solution**: Improve scan quality, use manual text entry for critical fields

#### Template Matching Failures

- **Cause**: Documents with significantly different layouts
- **Solution**: Create multiple templates or use manual annotation

#### Large File Processing

- **Cause**: Images exceeding size limits
- **Solution**: Resize images before upload or use the automatic resizing

#### WebSocket Connection Issues

- **Cause**: Network connectivity problems
- **Solution**: Check internet connection, refresh the page

### Performance Tips

1. **Batch Processing**: Process multiple similar documents together
2. **Template Reuse**: Maximize template usage to reduce manual work
3. **Selective OCR**: Only run OCR on regions that need extraction
4. **Regular Cleanup**: Archive old documents to maintain performance

## Advanced Features

### Batch Processing

1. Create batch jobs for processing multiple documents
2. Monitor progress through the batch status dashboard
3. Review results and apply corrections as needed

### WebSocket Events

The system provides real-time updates through WebSocket events:

- Document upload progress
- OCR processing status
- Template application results
- Batch job completion

### API Integration

For advanced users, the data processor provides a REST API for:

- Programmatic document upload
- Automated template application
- Batch processing management
- Custom export formats

## Support

For additional help:

1. Check the template library for examples
2. Review existing annotations in your channel
3. Contact your team administrator for template creation assistance
4. Refer to the API documentation for advanced integration options
