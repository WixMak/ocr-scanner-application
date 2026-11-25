import type { CSSProperties } from 'react';
import type { BoundingBox, PageSize } from '../../api/schemas';

export type ImageSize = { width: number; height: number };

export const toImageSize = (page: PageSize): ImageSize => ({
  width: page.imageWidth,
  height: page.imageHeight,
});
export type BoxDelta = { deltaX: number; deltaY: number };
export type BoxDimension = keyof BoundingBox;

export const BOX_DIMENSIONS: BoxDimension[] = ['x', 'y', 'width', 'height'];

export const MIN_BOX_SIZE_PX = 12;
const DEFAULT_BOX_WIDTH_RATIO = 0.3;
const DEFAULT_BOX_HEIGHT_RATIO = 0.04;
const PERCENT = 100;

const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), Math.max(min, max));

export const moveBox = (box: BoundingBox, delta: BoxDelta, image: ImageSize): BoundingBox => ({
  ...box,
  x: clamp(Math.round(box.x + delta.deltaX), 0, image.width - box.width),
  y: clamp(Math.round(box.y + delta.deltaY), 0, image.height - box.height),
});

export const resizeBox = (box: BoundingBox, delta: BoxDelta, image: ImageSize): BoundingBox => ({
  ...box,
  width: clamp(Math.round(box.width + delta.deltaX), MIN_BOX_SIZE_PX, image.width - box.x),
  height: clamp(Math.round(box.height + delta.deltaY), MIN_BOX_SIZE_PX, image.height - box.y),
});

export const setBoxDimension = (
  box: BoundingBox,
  dimension: BoxDimension,
  value: number,
  image: ImageSize,
): BoundingBox => {
  const rounded = Math.round(value);
  switch (dimension) {
    case 'x':
      return { ...box, x: clamp(rounded, 0, image.width - box.width) };
    case 'y':
      return { ...box, y: clamp(rounded, 0, image.height - box.height) };
    case 'width':
      return { ...box, width: clamp(rounded, MIN_BOX_SIZE_PX, image.width - box.x) };
    case 'height':
      return { ...box, height: clamp(rounded, MIN_BOX_SIZE_PX, image.height - box.y) };
  }
};

export const createDefaultBox = (image: ImageSize): BoundingBox => {
  const width = Math.max(Math.round(image.width * DEFAULT_BOX_WIDTH_RATIO), MIN_BOX_SIZE_PX);
  const height = Math.max(Math.round(image.height * DEFAULT_BOX_HEIGHT_RATIO), MIN_BOX_SIZE_PX);
  return {
    x: Math.round((image.width - width) / 2),
    y: Math.round((image.height - height) / 2),
    width,
    height,
  };
};

export const enclosingBox = (boxes: BoundingBox[]): BoundingBox => {
  const left = Math.min(...boxes.map((box) => box.x));
  const top = Math.min(...boxes.map((box) => box.y));
  const right = Math.max(...boxes.map((box) => box.x + box.width));
  const bottom = Math.max(...boxes.map((box) => box.y + box.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
};

export const toOverlayPosition = (box: BoundingBox, image: ImageSize): CSSProperties => ({
  left: `${(box.x / image.width) * PERCENT}%`,
  top: `${(box.y / image.height) * PERCENT}%`,
  width: `${(box.width / image.width) * PERCENT}%`,
  height: `${(box.height / image.height) * PERCENT}%`,
});
