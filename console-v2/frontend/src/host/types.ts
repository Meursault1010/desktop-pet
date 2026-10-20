import type { Message } from '../bridge';

export type DesktopEvent = {kind:string;text:string;at:number};
export type DesktopSnapshot = {
  clipboard:{id:string;text:string;at:number}[];clipboardPaused:boolean;
  media:{available:boolean;title?:string;artist?:string;app?:string;status?:string;position?:number;duration?:number};
  battery:{available:boolean;percent?:number;status?:number};
  drives?:string[];events:DesktopEvent[];
  weather:null|{city:string;region?:string;temperature_2m?:number;apparent_temperature?:number;relative_humidity_2m?:number;weather_code?:number;wind_speed_10m?:number;high?:number;low?:number;at:number};
  city:string;inbox:string;
};
export type ModelConfigSnapshot = {endpoint:string;model:string;keyPresent:boolean;keyPersistent:boolean};

export interface DesktopHost {
  readonly kind: 'electron' | 'tauri';
  request(name: string, payload: Record<string, unknown>): Promise<Message>;
  subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void): Promise<() => void>;
  reconnect(): Promise<void>;
  exit(): Promise<void>;
  aiModels?(): Promise<{endpoint:string;models:string[];preferredModel?:string}>;
  aiChat?(payload: {id:string;model:string;messages:{role:'user'|'assistant';content:string}[]}): Promise<{text:string}>;
  aiCancel?(): Promise<void>;
  aiSubscribe?(listener:(update:{id:string;phase:string;text:string})=>void):()=>void;
  desktopSnapshot?():Promise<DesktopSnapshot>;
  desktopAction?(input:{name:string;value?:unknown}):Promise<DesktopSnapshot>;
  desktopSubscribe?(listener:(event:DesktopEvent)=>void):()=>void;
  modelConfig?():Promise<ModelConfigSnapshot>;
  modelConfigSet?(input:{endpoint:string;model:string;apiKey?:string;clearKey?:boolean}):Promise<ModelConfigSnapshot>;
}

declare global {
  interface Window { yukiHost?: DesktopHost }
}
