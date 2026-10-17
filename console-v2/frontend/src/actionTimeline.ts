/** After the first pass, repeat only the operating segment (zero-based loopStart). */
export function loopPosition(position: number, durations: number[], loopStart = 0): number {
  const total = durations.reduce((a,b)=>a+b,0);
  if (position < total) return position;
  const intro = durations.slice(0,loopStart).reduce((a,b)=>a+b,0);
  return intro + (position-total) % (total-intro);
}
