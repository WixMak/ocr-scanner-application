import { useRef, type KeyboardEvent, type PointerEvent } from 'react';
import type { BoundingBox, FieldType } from '../../api/schemas';
import {
  moveBox,
  resizeBox,
  toOverlayPosition,
  type BoxDelta,
  type ImageSize,
} from './boxGeometry';
import { FieldTypeIcon } from './FieldTypeIcon';

export const KEYBOARD_STEP_PX = 5;

const ARROW_KEY_DELTAS: Record<string, BoxDelta> = {
  ArrowLeft: { deltaX: -KEYBOARD_STEP_PX, deltaY: 0 },
  ArrowRight: { deltaX: KEYBOARD_STEP_PX, deltaY: 0 },
  ArrowUp: { deltaX: 0, deltaY: -KEYBOARD_STEP_PX },
  ArrowDown: { deltaX: 0, deltaY: KEYBOARD_STEP_PX },
};

type DragMode = 'move' | 'resize';

type DragSession = {
  mode: DragMode;
  startX: number;
  startY: number;
  startBox: BoundingBox;
  imagePixelsPerScreenPixel: number;
};

export type BoxCanvas = {
  imageSize: ImageSize;
  instructionsId: string;
  getImagePixelsPerScreenPixel: () => number;
};

export type FieldBoxTag = {
  text: string;
  fieldType: FieldType;
};

type EditableFieldBoxProps = {
  box: BoundingBox;
  tag: FieldBoxTag;
  accessibleName: string;
  isSelected: boolean;
  canvas: BoxCanvas;
  onSelect: () => void;
  onBoxChange: (box: BoundingBox) => void;
};

export const EditableFieldBox = ({
  box,
  tag,
  accessibleName,
  isSelected,
  canvas,
  onSelect,
  onBoxChange,
}: EditableFieldBoxProps) => {
  const { imageSize, instructionsId, getImagePixelsPerScreenPixel } = canvas;
  const dragSession = useRef<DragSession | null>(null);

  const startDrag = (event: PointerEvent<HTMLElement>, mode: DragMode) => {
    event.stopPropagation();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragSession.current = {
      mode,
      startX: event.clientX,
      startY: event.clientY,
      startBox: box,
      imagePixelsPerScreenPixel: getImagePixelsPerScreenPixel(),
    };
    onSelect();
  };

  const continueDrag = (event: PointerEvent<HTMLElement>) => {
    const session = dragSession.current;
    if (!session) {
      return;
    }
    const delta = {
      deltaX: (event.clientX - session.startX) * session.imagePixelsPerScreenPixel,
      deltaY: (event.clientY - session.startY) * session.imagePixelsPerScreenPixel,
    };
    const updatedBox =
      session.mode === 'move'
        ? moveBox(session.startBox, delta, imageSize)
        : resizeBox(session.startBox, delta, imageSize);
    onBoxChange(updatedBox);
  };

  const endDrag = () => {
    dragSession.current = null;
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const delta = ARROW_KEY_DELTAS[event.key];
    if (!delta) {
      return;
    }
    event.preventDefault();
    const updatedBox = event.shiftKey
      ? resizeBox(box, delta, imageSize)
      : moveBox(box, delta, imageSize);
    onBoxChange(updatedBox);
  };

  return (
    <button
      type="button"
      className={`field-box field-type--${tag.fieldType}${isSelected ? ' field-box--selected' : ''}`}
      style={toOverlayPosition(box, imageSize)}
      aria-pressed={isSelected}
      aria-label={accessibleName}
      aria-describedby={instructionsId}
      onFocus={onSelect}
      onKeyDown={handleKeyDown}
      onPointerDown={(event) => startDrag(event, 'move')}
      onPointerMove={continueDrag}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
    >
      <span className="field-box__tag" aria-hidden="true">
        <FieldTypeIcon fieldType={tag.fieldType} className="icon--xs" />
        <span className="field-box__tag-text">{tag.text}</span>
      </span>
      <span
        className="field-box__resize-handle"
        aria-hidden="true"
        onPointerDown={(event) => startDrag(event, 'resize')}
        onPointerMove={continueDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      />
    </button>
  );
};
