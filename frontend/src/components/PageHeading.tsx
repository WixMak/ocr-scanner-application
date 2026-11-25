import type { ReactNode } from 'react';

const focusOnMount = (heading: HTMLHeadingElement | null) => heading?.focus();

export const PageHeading = ({ children }: { children: ReactNode }) => (
  <h1 ref={focusOnMount} tabIndex={-1} className="page-heading">
    {children}
  </h1>
);
