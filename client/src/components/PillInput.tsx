/**
 * PillInput — multi-value input with pill tokens.
 *
 * Behaviors:
 * - Enter/comma adds a pill
 * - Backspace on empty input removes the last pill
 * - × button removes a specific pill
 * - Deduplicates silently
 */

import { useState, useRef, type KeyboardEvent } from 'react';

interface PillInputProps {
  id: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}

export function PillInput({ id, values, onChange, placeholder }: PillInputProps) {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  function addPill(raw: string) {
    const trimmed = raw.trim().toLowerCase();
    if (!trimmed) return;
    if (values.includes(trimmed)) {
      setInputValue('');
      return;
    }
    onChange([...values, trimmed]);
    setInputValue('');
  }

  function removePill(index: number) {
    onChange(values.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if ((e.key === 'Enter' || e.key === ',') && inputValue.trim()) {
      e.preventDefault();
      addPill(inputValue);
    } else if (e.key === 'Backspace' && !inputValue && values.length > 0) {
      removePill(values.length - 1);
    }
  }

  return (
    <div
      className="pill-input"
      onClick={() => inputRef.current?.focus()}
    >
      {values.map((val, i) => (
        <span key={val} className="pill">
          {val}
          <button
            type="button"
            className="pill-x"
            onClick={(e) => { e.stopPropagation(); removePill(i); }}
            aria-label={`Remove ${val}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        id={id}
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (inputValue.trim()) addPill(inputValue); }}
        placeholder={values.length === 0 ? placeholder : ''}
      />
    </div>
  );
}
