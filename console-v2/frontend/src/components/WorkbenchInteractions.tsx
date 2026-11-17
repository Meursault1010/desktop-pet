import {useEffect, useId, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import '../interactions.css';

type Hint = {target: HTMLElement; text: string};
const scope = '.observatory, .dialog-content';
const hintSelector = '[title], [data-tooltip], button[aria-label], [role="button"][aria-label]';

/** One tooltip layer for workbench controls, including controls rendered in a dialog portal. */
export function WorkbenchInteractions({hints}: {hints: boolean}) {
  const id = useId();
  const tooltip = useRef<HTMLDivElement>(null);
  const [hint, setHint] = useState<Hint | null>(null);
  const [position, setPosition] = useState({left: 0, top: 0, ready: false});

  useEffect(() => {
    const titles = new Map<HTMLElement, string>();
    let pointer: HTMLElement | null = null;
    let focus: HTMLElement | null = null;
    let current: HTMLElement | null = null;
    let dismissed: HTMLElement | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closing: ReturnType<typeof setTimeout> | undefined;

    // Empty title suppresses the browser's inherited tooltip. Keep the authored value
    // separately so React can still update/remove the attribute as control state changes.
    function captureTitle(element: HTMLElement) {
      if (!element.closest(scope)) return;
      const title = element.getAttribute('title');
      if (title) { titles.set(element, title); element.setAttribute('title', ''); }
    }
    function scan(node: ParentNode) {
      if (node instanceof HTMLElement && node.hasAttribute('title')) captureTitle(node);
      node.querySelectorAll<HTMLElement>('[title]').forEach(captureTitle);
    }
    function textFor(target: HTMLElement) {
      const explicit = target.dataset.tooltip ?? titles.get(target);
      const visible = (target.innerText || '').replace(/\s+/g, ' ').trim();
      const text = (explicit || (!visible ? target.getAttribute('aria-label') : '') || '').trim();
      // A label already visible on a button needs no duplicate floating label.
      return target.matches('button, [role="button"]') && text === visible ? '' : text;
    }
    function targetFor(node: EventTarget | null) {
      if (!(node instanceof Element)) return null;
      const target = node.closest<HTMLElement>(hintSelector);
      return target?.closest(scope) && textFor(target) ? target : null;
    }
    function clearDescription() {
      if (!current) return;
      const remaining = (current.getAttribute('aria-describedby') || '').split(/\s+/).filter(value => value && value !== id);
      if (remaining.length) current.setAttribute('aria-describedby', remaining.join(' '));
      else current.removeAttribute('aria-describedby');
      current = null;
    }
    function hide() {
      clearTimeout(timer); clearTimeout(closing);
      clearDescription(); setHint(null);
    }
    function show(target: HTMLElement, delay: number) {
      clearTimeout(closing);
      if (current === target || dismissed === target || !hints) return;
      hide();
      timer = setTimeout(() => {
        const text = textFor(target);
        if (!target.isConnected || !target.getClientRects().length || !text) return;
        current = target;
        const described = (target.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
        target.setAttribute('aria-describedby', [...new Set([...described, id])].join(' '));
        setPosition(value => ({...value, ready: false}));
        setHint({target, text});
      }, delay);
    }
    function leave() {
      clearTimeout(closing);
      closing = setTimeout(() => {
        if (tooltip.current?.matches(':hover')) return;
        const target = focus || pointer;
        if (target) show(target, 0); else hide();
      }, 90);
    }
    function pointerOver(event: PointerEvent) {
      if (event.pointerType === 'touch') return;
      if (tooltip.current?.contains(event.target as Node)) { clearTimeout(closing); return; }
      const next = targetFor(event.target);
      if (next === pointer) return;
      dismissed = null;
      pointer = next;
      if (next) show(next, 420); else leave();
    }
    function pointerOut(event: PointerEvent) {
      if (pointer?.contains(event.relatedTarget as Node)) return;
      if (pointer === dismissed) dismissed = null;
      pointer = null; leave();
    }
    function focusIn(event: FocusEvent) {
      const next = targetFor(event.target);
      if (next !== focus) dismissed = null;
      focus = next?.matches(':focus-visible') ? next : null;
      if (focus) show(focus, 80);
    }
    function focusOut() { if (focus === dismissed) dismissed = null; focus = null; leave(); }
    function dismiss() { dismissed = current || pointer || focus; hide(); }
    function keyDown(event: KeyboardEvent) { if (event.key === 'Escape') dismiss(); }
    function visibility() { if (document.hidden) dismiss(); }

    scan(document.body);
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'childList') {
          record.addedNodes.forEach(node => { if (node instanceof HTMLElement) scan(node); });
        } else if (record.target instanceof HTMLElement) {
          const target = record.target;
          if (target.getAttribute('title')) captureTitle(target);
          else if (record.oldValue === '') titles.delete(target);
        }
      }
      for (const target of titles.keys()) if (!target.isConnected) titles.delete(target);
      if (current && (!current.isConnected || !current.getClientRects().length)) hide();
      else if (current) {
        const text = textFor(current);
        if (text) setHint(value => value?.text === text ? value : {target: current!, text});
        else hide();
      }
    });
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['title'], attributeOldValue: true});
    document.addEventListener('pointerover', pointerOver, true);
    document.addEventListener('pointerout', pointerOut, true);
    document.addEventListener('focusin', focusIn, true);
    document.addEventListener('focusout', focusOut, true);
    document.addEventListener('pointerdown', dismiss, true);
    document.addEventListener('keydown', keyDown, true);
    document.addEventListener('scroll', dismiss, true);
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('resize', dismiss);
    window.addEventListener('blur', dismiss);
    return () => {
      observer.disconnect(); hide();
      titles.forEach((title, target) => { if (target.getAttribute('title') === '') target.setAttribute('title', title); });
      document.removeEventListener('pointerover', pointerOver, true);
      document.removeEventListener('pointerout', pointerOut, true);
      document.removeEventListener('focusin', focusIn, true);
      document.removeEventListener('focusout', focusOut, true);
      document.removeEventListener('pointerdown', dismiss, true);
      document.removeEventListener('keydown', keyDown, true);
      document.removeEventListener('scroll', dismiss, true);
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('resize', dismiss);
      window.removeEventListener('blur', dismiss);
    };
  }, [hints, id]);

  useLayoutEffect(() => {
    if (!hint || !tooltip.current) return;
    const anchor = hint.target.getBoundingClientRect();
    const box = tooltip.current.getBoundingClientRect();
    const margin = 10, gap = 8;
    const above = anchor.top - box.height - gap;
    const top = above >= margin ? above : Math.min(window.innerHeight - box.height - margin, anchor.bottom + gap);
    const left = Math.min(window.innerWidth - box.width - margin, Math.max(margin, anchor.left + (anchor.width - box.width) / 2));
    setPosition({left: Math.max(margin, left), top: Math.max(margin, top), ready: true});
  }, [hint]);

  return hint && hints ? createPortal(<div ref={tooltip} id={id} role="tooltip" className="workbench-tooltip"
    data-ready={position.ready} style={{left: position.left, top: position.top}}>{hint.text}</div>, document.body) : null;
}
