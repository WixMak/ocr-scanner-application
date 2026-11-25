import { useState } from 'react';

type BoxDimensionInputProps = {
  id: string;
  label: string;
  value: number;
  onFocus: () => void;
  onCommit: (value: number) => void;
};

export const BoxDimensionInput = ({ id, label, value, onFocus, onCommit }: BoxDimensionInputProps) => {
  const [typedValue, setTypedValue] = useState<string | null>(null);

  const handleChange = (rawValue: string) => {
    setTypedValue(rawValue);
    const parsed = Number.parseInt(rawValue, 10);
    if (!Number.isNaN(parsed)) {
      onCommit(parsed);
    }
  };

  return (
    <div className="form-control">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="input input--mono"
        type="number"
        inputMode="numeric"
        min={0}
        value={typedValue ?? value}
        onFocus={onFocus}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={() => setTypedValue(null)}
      />
    </div>
  );
};
