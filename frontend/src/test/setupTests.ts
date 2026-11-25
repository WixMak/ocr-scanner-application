import '@testing-library/jest-dom';
import { initI18n } from '../i18n';

void initI18n('en');

// jsdom has no PointerEvent; without it Testing Library drops clientX/pointerId from pointer events.
class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}

if (!('PointerEvent' in window)) {
  Object.assign(window, { PointerEvent: TestPointerEvent });
}

afterEach(() => {
  jest.restoreAllMocks();
  window.location.hash = '';
});
