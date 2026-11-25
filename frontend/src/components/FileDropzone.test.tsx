import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from '../test/renderWithProviders';
import { FileDropzone } from './FileDropzone';

describe('FileDropzone', () => {
  it('highlights the drop area while a file is dragged over it', () => {
    renderWithProviders(<FileDropzone id="upload" label="Blank form" onFileSelected={jest.fn()} />);
    const input = screen.getByLabelText('Blank form');
    const dropArea = input.closest('label');

    fireEvent.dragEnter(input);
    expect(dropArea).toHaveClass('dropzone--active');

    fireEvent.dragLeave(input);
    expect(dropArea).not.toHaveClass('dropzone--active');

    fireEvent.dragEnter(input);
    fireEvent.drop(input);
    expect(dropArea).not.toHaveClass('dropzone--active');
  });

  it('ignores a selection that was cancelled', () => {
    const onFileSelected = jest.fn();
    renderWithProviders(<FileDropzone id="upload" label="Blank form" onFileSelected={onFileSelected} />);

    fireEvent.change(screen.getByLabelText('Blank form'), { target: { files: [] } });

    expect(onFileSelected).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('is disabled while a previous file is being processed', () => {
    renderWithProviders(
      <FileDropzone id="upload" label="Blank form" isDisabled onFileSelected={jest.fn()} />,
    );

    expect(screen.getByLabelText('Blank form')).toBeDisabled();
  });
});
