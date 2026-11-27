/** A sparse celestial signature for yuki's display stage. Never interactive. */
export function StarField(){
  return <svg className="star-field" viewBox="0 0 320 320" fill="none" aria-hidden="true">
    <path className="star-trail" d="M31 110C65 30 235 20 290 102"/>
    <path className="constellation" d="m43 102 29-45 59 13"/>
    <g className="star-points"><circle cx="43" cy="102" r="1.5"/><circle cx="72" cy="57" r="2"/><circle cx="131" cy="70" r="1.3"/><circle cx="280" cy="163" r="1.3"/><circle cx="45" cy="238" r="1.5"/></g>
    <path className="star-glint glint-one" d="m258 53 2.7 9.3L270 65l-9.3 2.7L258 77l-2.7-9.3L246 65l9.3-2.7Z"/>
    <path className="star-glint glint-two" d="m49 161 1.8 6.2L57 169l-6.2 1.8L49 177l-1.8-6.2L41 169l6.2-1.8Z"/>
    <path className="star-glint glint-three" d="m269 228 1.5 5.5 5.5 1.5-5.5 1.5-1.5 5.5-1.5-5.5-5.5-1.5 5.5-1.5Z"/>
  </svg>;
}
