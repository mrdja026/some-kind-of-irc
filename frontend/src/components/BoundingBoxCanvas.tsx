import { useRef, useEffect, useState, useCallback } from 'react'
import type { Annotation } from '../types'

// Fabric.js types are complex, we'll use any for the canvas instance
// The actual fabric import happens client-side only
let fabric: any = null

interface BoundingBoxCanvasProps {
  documentId: string
  imageUrl?: string
  annotations: Annotation[]
  selectedAnnotation: Annotation | null
  onSelectAnnotation: (annotation: Annotation | null) => void
  onCreateAnnotation: (box: {
    x: number
    y: number
    width: number
    height: number
  }) => void
  onUpdateAnnotation: (
    id: string,
    box: { x: number; y: number; width: number; height: number },
  ) => void
  tool: 'select' | 'draw'
  zoom: number
  activeColor: string
}

export function BoundingBoxCanvas({
  documentId,
  imageUrl,
  annotations,
  selectedAnnotation,
  onSelectAnnotation,
  onCreateAnnotation,
  onUpdateAnnotation,
  tool,
  zoom,
  activeColor,
}: BoundingBoxCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fabricRef = useRef<any>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(
    null,
  )
  const [tempRect, setTempRect] = useState<any>(null)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageSize, setImageSize] = useState<{
    width: number
    height: number
  } | null>(null)

  // Load Fabric.js dynamically (client-side only)
  useEffect(() => {
    if (typeof window !== 'undefined' && !fabric) {
      import('fabric').then((module: any) => {
        fabric = module.fabric || module
      })
    }
  }, [])

  // Initialize canvas
  useEffect(() => {
    if (!canvasRef.current || !fabric) return

    const canvas = new fabric.Canvas(canvasRef.current, {
      selection: tool === 'select',
      preserveObjectStacking: true,
    })
    fabricRef.current = canvas

    // Handle object selection
    canvas.on('selection:created', (e: any) => {
      const obj = e.selected?.[0]
      if (obj?.annotationId) {
        const annotation = annotations.find((a) => a.id === obj.annotationId)
        if (annotation) {
          onSelectAnnotation(annotation)
        }
      }
    })

    canvas.on('selection:cleared', () => {
      onSelectAnnotation(null)
    })

    // Handle object modification
    canvas.on('object:modified', (e: any) => {
      const obj = e.target
      if (obj?.annotationId) {
        const scaleX = obj.scaleX || 1
        const scaleY = obj.scaleY || 1
        onUpdateAnnotation(obj.annotationId, {
          x: obj.left,
          y: obj.top,
          width: obj.width * scaleX,
          height: obj.height * scaleY,
        })
        // Reset scale after getting dimensions
        obj.set({ scaleX: 1, scaleY: 1 })
        obj.setCoords()
      }
    })

    return () => {
      canvas.dispose()
      fabricRef.current = null
    }
  }, [fabric, tool])

  // Load background image
  useEffect(() => {
    if (!fabricRef.current || !imageUrl || !fabric) return

    const canvas = fabricRef.current

    fabric.Image.fromURL(
      imageUrl,
      (img: any) => {
        if (!img) return

        // Set canvas size based on image
        const maxWidth = containerRef.current?.clientWidth || 800
        const maxHeight = containerRef.current?.clientHeight || 600

        const scale = Math.min(maxWidth / img.width, maxHeight / img.height, 1)

        const scaledWidth = img.width * scale
        const scaledHeight = img.height * scale

        canvas.setWidth(scaledWidth)
        canvas.setHeight(scaledHeight)
        setImageSize({ width: scaledWidth, height: scaledHeight })

        img.set({
          selectable: false,
          evented: false,
          scaleX: scale,
          scaleY: scale,
        })

        canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas))
        setImageLoaded(true)
      },
      { crossOrigin: 'anonymous' },
    )
  }, [imageUrl, fabric])

  // Apply zoom
  useEffect(() => {
    if (!fabricRef.current) return
    const canvas = fabricRef.current
    canvas.setZoom(zoom)

    if (imageSize) {
      canvas.setWidth(imageSize.width * zoom)
      canvas.setHeight(imageSize.height * zoom)
    }

    canvas.renderAll()
  }, [zoom, imageSize])

  // Update selection mode based on tool
  useEffect(() => {
    if (!fabricRef.current) return
    fabricRef.current.selection = tool === 'select'

    // Make objects selectable/unselectable based on tool
    fabricRef.current.getObjects().forEach((obj: any) => {
      if (obj.type === 'rect' && obj.annotationId) {
        obj.set({
          selectable: tool === 'select',
          evented: tool === 'select',
        })
      }
    })

    fabricRef.current.renderAll()
  }, [tool])

  // Sync annotations with canvas objects
  useEffect(() => {
    if (!fabricRef.current || !fabric || !imageLoaded) return

    const canvas = fabricRef.current

    // Remove existing annotation rectangles
    const objects = canvas.getObjects().filter((obj: any) => obj.annotationId)
    objects.forEach((obj: any) => canvas.remove(obj))

    // Add rectangles for each annotation
    annotations.forEach((annotation) => {
      const rect = new fabric.Rect({
        left: annotation.bounding_box.x,
        top: annotation.bounding_box.y,
        width: annotation.bounding_box.width,
        height: annotation.bounding_box.height,
        fill: `${annotation.color}33`,
        stroke: annotation.color,
        strokeWidth: 2,
        selectable: tool === 'select',
        evented: tool === 'select',
        cornerColor: annotation.color,
        cornerStyle: 'circle',
        cornerSize: 8,
        transparentCorners: false,
        annotationId: annotation.id,
      })

      canvas.add(rect)

      // Select if this is the selected annotation
      if (selectedAnnotation?.id === annotation.id) {
        canvas.setActiveObject(rect)
      }
    })

    canvas.renderAll()
  }, [annotations, fabric, imageLoaded, tool, selectedAnnotation])

  // Handle mouse events for drawing
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (tool !== 'draw' || !fabricRef.current) return

      const canvas = fabricRef.current
      const pointer = canvas.getPointer(e.nativeEvent)

      setIsDrawing(true)
      setDrawStart({ x: pointer.x, y: pointer.y })

      // Create temporary rectangle
      const rect = new fabric.Rect({
        left: pointer.x,
        top: pointer.y,
        width: 0,
        height: 0,
        fill: `${activeColor}33`,
        stroke: activeColor,
        strokeWidth: 2,
        selectable: false,
        evented: false,
      })

      canvas.add(rect)
      setTempRect(rect)
    },
    [tool, activeColor, fabric],
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !drawStart || !tempRect || !fabricRef.current) return

      const canvas = fabricRef.current
      const pointer = canvas.getPointer(e.nativeEvent)

      const left = Math.min(drawStart.x, pointer.x)
      const top = Math.min(drawStart.y, pointer.y)
      const width = Math.abs(pointer.x - drawStart.x)
      const height = Math.abs(pointer.y - drawStart.y)

      tempRect.set({
        left,
        top,
        width,
        height,
      })

      canvas.renderAll()
    },
    [isDrawing, drawStart, tempRect],
  )

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !drawStart || !fabricRef.current) return

      const canvas = fabricRef.current
      const pointer = canvas.getPointer(e.nativeEvent)

      const left = Math.min(drawStart.x, pointer.x)
      const top = Math.min(drawStart.y, pointer.y)
      const width = Math.abs(pointer.x - drawStart.x)
      const height = Math.abs(pointer.y - drawStart.y)

      // Only create annotation if the rectangle is large enough
      if (width > 10 && height > 10) {
        onCreateAnnotation({
          x: left,
          y: top,
          width,
          height,
        })
      }

      // Remove temporary rectangle
      if (tempRect) {
        canvas.remove(tempRect)
      }

      setIsDrawing(false)
      setDrawStart(null)
      setTempRect(null)
    },
    [isDrawing, drawStart, tempRect, onCreateAnnotation],
  )

  // Pan functionality
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(
    null,
  )
  const [viewportOffset, setViewportOffset] = useState({ x: 0, y: 0 })

  const handlePanStart = useCallback(
    (e: React.MouseEvent) => {
      if (tool === 'select' && e.shiftKey) {
        setIsPanning(true)
        setPanStart({
          x: e.clientX - viewportOffset.x,
          y: e.clientY - viewportOffset.y,
        })
      }
    },
    [tool, viewportOffset],
  )

  const handlePanMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isPanning || !panStart) return
      setViewportOffset({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      })
    },
    [isPanning, panStart],
  )

  const handlePanEnd = useCallback(() => {
    setIsPanning(false)
    setPanStart(null)
  }, [])

  return (
    <div
      ref={containerRef}
      className="w-full h-full overflow-auto flex items-center justify-center"
      style={{
        cursor:
          tool === 'draw' ? 'crosshair' : isPanning ? 'grabbing' : 'default',
      }}
      onMouseDown={tool === 'select' ? handlePanStart : handleMouseDown}
      onMouseMove={
        tool === 'select' && isPanning ? handlePanMove : handleMouseMove
      }
      onMouseUp={tool === 'select' && isPanning ? handlePanEnd : handleMouseUp}
      onMouseLeave={
        tool === 'select' && isPanning ? handlePanEnd : handleMouseUp
      }
    >
      <div
        style={{
          transform: `translate(${viewportOffset.x}px, ${viewportOffset.y}px)`,
          transition: isPanning ? 'none' : 'transform 0.1s ease',
        }}
      >
        {!imageUrl && (
          <div className="flex items-center justify-center w-full h-full min-h-[400px] text-gray-500">
            No image available
          </div>
        )}
        <canvas ref={canvasRef} className={imageUrl ? '' : 'hidden'} />
      </div>
    </div>
  )
}
