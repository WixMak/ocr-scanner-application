import {
  MIN_BOX_SIZE_PX,
  createDefaultBox,
  enclosingBox,
  moveBox,
  resizeBox,
  setBoxDimension,
  toOverlayPosition,
} from './boxGeometry';

const IMAGE = { width: 1000, height: 500 };
const BOX = { x: 100, y: 100, width: 200, height: 50 };

describe('boxGeometry', () => {
  it('finds the smallest box that covers every given box', () => {
    const farBox = { x: 600, y: 40, width: 30, height: 30 };

    expect(enclosingBox([BOX])).toEqual(BOX);
    expect(enclosingBox([BOX, farBox])).toEqual({ x: 100, y: 40, width: 530, height: 110 });
  });

  it('moves a box and keeps it inside the image', () => {
    expect(moveBox(BOX, { deltaX: 10.4, deltaY: -5.6 }, IMAGE)).toEqual({ ...BOX, x: 110, y: 94 });
    expect(moveBox(BOX, { deltaX: 5000, deltaY: -5000 }, IMAGE)).toEqual({ ...BOX, x: 800, y: 0 });
  });

  it('resizes a box between the minimum size and the image edge', () => {
    expect(resizeBox(BOX, { deltaX: 50, deltaY: 10 }, IMAGE)).toEqual({ ...BOX, width: 250, height: 60 });
    expect(resizeBox(BOX, { deltaX: -1000, deltaY: 5000 }, IMAGE)).toEqual({
      ...BOX,
      width: MIN_BOX_SIZE_PX,
      height: 400,
    });
  });

  it.each([
    ['x', 950, { ...BOX, x: 800 }],
    ['y', -20, { ...BOX, y: 0 }],
    ['width', 2000, { ...BOX, width: 900 }],
    ['height', 3, { ...BOX, height: MIN_BOX_SIZE_PX }],
  ] as const)('sets %s with clamping', (dimension, value, expected) => {
    expect(setBoxDimension(BOX, dimension, value, IMAGE)).toEqual(expected);
  });

  it('creates a centred default box', () => {
    expect(createDefaultBox(IMAGE)).toEqual({ x: 350, y: 240, width: 300, height: 20 });
  });

  it('never makes a default box smaller than the minimum', () => {
    const box = createDefaultBox({ width: 20, height: 20 });
    expect(box.width).toBe(MIN_BOX_SIZE_PX);
    expect(box.height).toBe(MIN_BOX_SIZE_PX);
  });

  it('converts a box to percentage overlay position', () => {
    expect(toOverlayPosition(BOX, IMAGE)).toEqual({
      left: '10%',
      top: '20%',
      width: '20%',
      height: '10%',
    });
  });
});
