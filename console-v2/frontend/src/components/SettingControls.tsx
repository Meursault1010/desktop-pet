import { useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import * as Switch from '@radix-ui/react-switch';
import { LoaderCircle, RotateCcw } from './Icons';
import { parseSettingNumber } from '../commandQueue';

export function Toggle({ label, description, checked, disabled, pending, reason, onChange }: {
  label: string; description?: string; checked: boolean; disabled?: boolean;
  pending?: boolean; reason?: string; onChange: (value: boolean) => void;
}) {
  const id = useId();
  return <div className={`setting-row ${disabled ? 'is-disabled' : ''}`} aria-busy={pending}>
    <span><label htmlFor={id} className="setting-label">{label}</label>
      <span id={`${id}-hint`} className="setting-description">{reason || description}</span></span>
    {pending && <LoaderCircle className="spin pending-icon" size={15} aria-label="正在应用"/>}
    <Switch.Root id={id} className="toggle" checked={checked} disabled={disabled || pending}
      onCheckedChange={onChange} aria-label={label} aria-describedby={`${id}-hint`}>
      <Switch.Thumb className="toggle-thumb"/>
    </Switch.Root>
  </div>;
}

export function Range({ label, description, value, min, max, unit, disabled, pending, defaultValue, onCommit }: {
  label: string; description: string; value: number; min: number; max: number;
  unit: string; disabled: boolean; pending?: boolean; defaultValue: number;
  onCommit: (value: number) => Promise<boolean>;
}) {
  const id = useId();
  const [draft, setDraft] = useState(value);
  const [text, setText] = useState(String(value));
  const [error, setError] = useState('');
  const edited = useRef<string | null>(null);
  const current = useRef({ value, disabled, onCommit, min, max });
  current.current = { value, disabled, onCommit, min, max };
  const sequence = useRef(0);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // Numeric edits also survive navigation; invalid/empty drafts never reach IPC.
      if (edited.current !== null && !current.current.disabled) {
        const number = parseSettingNumber(edited.current, current.current.min, current.current.max);
        if (number !== null && number !== current.current.value) void current.current.onCommit(number);
      }
    };
  }, []);
  useEffect(() => {
    if (!pending && edited.current === null) { setDraft(value); setText(String(value)); }
  }, [value, pending]);

  const commit = (next: number) => {
    edited.current = null;
    setDraft(next); setText(String(next)); setError('');
    const request = ++sequence.current;
    if (next === value && !pending) return;
    // Enqueue immediately at app scope: changing pages cannot cancel the write.
    void onCommit(next).then(ok => {
      if (!ok && mounted.current && request === sequence.current) {
        setDraft(current.current.value); setText(String(current.current.value));
      }
    });
  };
  const commitText = () => {
    if (edited.current === null) return;
    const next = parseSettingNumber(edited.current, min, max);
    if (next === null) {
      edited.current = null; setDraft(value); setText(String(value));
      setError(`请输入 ${min}–${max} 之间的整数，已恢复当前值。`);
    } else commit(next);
  };

  return <div className="range-setting" aria-busy={pending}>
    <div className="range-heading"><label htmlFor={id}>{label}</label>
      <div className="range-tools"><span className="number-control">
        <input type="number" aria-label={`${label}数值`} aria-describedby={`${id}-hint ${id}-error`}
          aria-invalid={!!error} min={min} max={max} step={1} value={text} disabled={disabled}
          onChange={event => { edited.current = event.target.value; setText(event.target.value); setError(''); }}
          onBlur={commitText} onKeyDown={event => {
            if (event.key === 'Enter') { commitText(); event.currentTarget.blur(); }
            if (event.key === 'Escape') { edited.current = null; setDraft(value); setText(String(value)); setError(''); event.currentTarget.blur(); }
          }}/><span>{unit.trim()}</span></span>
        <button type="button" className="range-reset" disabled={disabled || (draft === defaultValue && !pending)}
          onClick={() => commit(defaultValue)} aria-label={`恢复${label}默认值 ${defaultValue}${unit}`}
          title={`恢复默认：${defaultValue}${unit}`}><RotateCcw size={14}/>默认</button>
      </div></div>
    <p id={`${id}-hint`}>{description}</p>
    <input id={id} type="range" min={min} max={max} step={1} value={draft} disabled={disabled}
      aria-describedby={`${id}-hint`} aria-valuetext={`${draft}${unit}`}
      style={{ '--progress': `${(draft - min) / (max - min) * 100}%` } as CSSProperties}
      onChange={event => commit(Number(event.target.value))}/>
    <div className="range-limits"><span>{min}{unit}</span><span className="range-state">
      {pending ? <><LoaderCircle className="spin" size={12}/>正在应用</> : `默认 ${defaultValue}${unit}`}
    </span><span>{max}{unit}</span></div>
    <p id={`${id}-error`} className="field-error" role={error ? 'alert' : undefined}>{error}</p>
  </div>;
}
