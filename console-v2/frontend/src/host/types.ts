import type { Message } from '../bridge';

export type DesktopEvent = {kind:string;text:string;at:number};
export type LyricsSettings={enabled:boolean;overlay:boolean;alwaysOnTop:boolean;autoFind:boolean;palette:'ice'|'white'|'rose'|'gold';style:'glass'|'plain'|'outline';opacity:number};
export type LyricsSnapshot={settings:LyricsSettings;key:string;timed:boolean;lines:{at:number;text:string}[];source:string;busy:boolean;error:string};
export type DesktopSnapshot = {
  system?:{cpu:number;memoryUsed:number;memoryTotal:number};autostart?:boolean;
  clipboard:{id:string;text:string;at:number}[];clipboardPaused:boolean;
  media:{available:boolean;title?:string;artist?:string;app?:string;status?:string;position?:number;duration?:number;start?:number;rate?:number;observedAt?:number;controls?:{play:boolean;pause:boolean;previous:boolean;next:boolean;seek?:boolean}};
  lyrics?:LyricsSnapshot;
  battery:{available:boolean;percent?:number;status?:number};
  drives?:string[];events:DesktopEvent[];
  weather:null|{city:string;region?:string;temperature_2m?:number;apparent_temperature?:number;relative_humidity_2m?:number;weather_code?:number;wind_speed_10m?:number;high?:number;low?:number;at:number};
  city:string;inbox:string;
};
export type ModelConfigSnapshot = {builtinEnabled?:boolean;endpoint:string;model:string;keyPresent:boolean;keyPersistent:boolean};
export type TranslationSnapshot={enabled:boolean;phase:string;source:string;text:string;error:string;target:string;method:string};

export type ChatAttachment={id:string;name:string;size:number;kind:'image'|'document';preview?:string;truncated:boolean;characters?:number;recognition?:'ocr'};

export interface DesktopHost {
  quickToolsSync?(value:{focus:import('../workspaceModel').Focus;todos:import('../workspaceModel').Todo[]}):Promise<void>;
  quickToolsSubscribe?(listener:(value:{name:string;value?:unknown})=>void):()=>void;
  workbenchConfig?():Promise<WorkbenchConfig>;
  workbenchSet?(input:Partial<WorkbenchConfig>):Promise<WorkbenchConfig>;
  windowMode?(wide:boolean):Promise<{wide:boolean}>;
  readonly kind: 'electron' | 'tauri';
  request(name: string, payload: Record<string, unknown>): Promise<Message>;
  subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void): Promise<() => void>;
  reconnect(): Promise<void>;
  exit(): Promise<void>;
  translationMode?(enabled?:boolean):Promise<TranslationSnapshot>;
  translationCapture?():Promise<void>;
  translationSubscribe?(listener:(state:TranslationSnapshot)=>void):()=>void;
  aiAttach?():Promise<ChatAttachment[]>;
  aiModels?(): Promise<{endpoint:string;models:string[];preferredModel?:string}>;
  aiChat?(payload: {id:string;model:string;messages:{role:'user'|'assistant';content:string;attachments?:string[]}[]}): Promise<{text:string}>;
  aiCancel?(): Promise<void>;
  aiSubscribe?(listener:(update:{id:string;phase:string;text:string})=>void):()=>void;
  desktopSnapshot?():Promise<DesktopSnapshot>;
  desktopAction?(input:{name:string;value?:unknown}):Promise<DesktopSnapshot>;
  desktopSubscribe?(listener:(event:DesktopEvent)=>void):()=>void;
  builtinModelSet?(enabled:boolean):Promise<ModelConfigSnapshot>;
  modelConfig?():Promise<ModelConfigSnapshot>;
  modelConfigSet?(input:{endpoint:string;model:string;apiKey?:string;clearKey?:boolean}):Promise<ModelConfigSnapshot>;
}
export type WorkbenchConfig={theme:'light'|'mist'|'dark';reduced:boolean;particles:boolean;bubble:'light'|'mist'|'dark';persona:string;memory:string;shortcuts:Record<string,string>;shortcutStatus?:Record<string,string>};

declare global {
  interface Window { yukiHost?: DesktopHost }
}
