import type { ReactNode, Ref } from 'react';
import type { ImageSize } from '../features/templates/boxGeometry';

type FormCanvasProps = {
  imageUrl: string;
  imageSize: ImageSize;
  imageAlt: string;
  canvasRef?: Ref<HTMLDivElement>;
  children: ReactNode;
};

export const FormCanvas = ({ imageUrl, imageSize, imageAlt, canvasRef, children }: FormCanvasProps) => (
  <div className="form-canvas-scroller">
    <div
      ref={canvasRef}
      className="form-canvas"
      style={{
        aspectRatio: `${imageSize.width} / ${imageSize.height}`,
        width: `min(100%, calc(var(--form-canvas-max-height) * ${imageSize.width} / ${imageSize.height}))`,
      }}
    >
      <img className="form-canvas__image" src={imageUrl} alt={imageAlt} draggable={false} />
      {children}
    </div>
  </div>
);
