import {useEffect, useState} from 'react';
import {command} from '../bridge';

const FRAME_INTERVAL = 1000 / 24;

export function CharacterPreview({live, hidden, opacity, scale}: {
  live: boolean;
  hidden: boolean;
  opacity: number;
  scale: number;
}) {
  const [frame, setFrame] = useState<string>();

  useEffect(() => {
    setFrame(undefined);
    if (!live) return;

    let disposed = false;
    let requesting = false;
    let timer: number | undefined;
    let visibility = 0;

    const poll = async () => {
      if (disposed || requesting || document.hidden) return;
      requesting = true;
      const started = performance.now();
      const currentVisibility = visibility;
      let delay = FRAME_INTERVAL;
      try {
        const response = await command('get_preview_frame');
        if (response.frame) {
          const image = new Image();
          image.src = response.frame;
          await image.decode();
          if (!disposed && currentVisibility === visibility && !document.hidden) {
            setFrame(response.frame);
          }
        }
      } catch {
        if (!disposed && currentVisibility === visibility) setFrame(undefined);
        delay = 500;
      } finally {
        requesting = false;
        if (!disposed && !document.hidden) {
          timer = window.setTimeout(poll, Math.max(0, delay - (performance.now() - started)));
        }
      }
    };

    const onVisibility = () => {
      visibility++;
      window.clearTimeout(timer);
      if (document.hidden) setFrame(undefined);
      else void poll();
    };
    document.addEventListener('visibilitychange', onVisibility);
    void poll();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [live]);

  const shownFrame = live ? frame : undefined;
  return <div className="character-stage">
    <div className="character-visual" style={{opacity, transform:`scale(${scale})`}}>
      <img src={shownFrame ?? '/pet-preview.png'} alt="yuki，白发蓝裙的猫耳伙伴" draggable={false}/>
    </div>
    {hidden&&<span className="stage-caption">桌宠已隐藏</span>}
  </div>;
}
