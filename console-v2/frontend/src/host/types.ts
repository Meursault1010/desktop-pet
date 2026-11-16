import type { Message } from '../bridge';

export type DesktopEvent = {kind:string;text:string;at:number};
export type ClipboardEntry={id:string;preview:string;chars:number;truncated:boolean;at:number};
export type LyricsSettings={enabled:boolean;overlay:boolean;alwaysOnTop:boolean;autoFind:boolean;palette:'ice'|'white'|'rose'|'gold';style:'glass'|'plain'|'outline';opacity:number};
export type LyricsSnapshot={settings:LyricsSettings;key:string;timed:boolean;lines:{at:number;text:string}[];source:string;busy:boolean;error:string};
export type DesktopSnapshot = {
  system?:{cpu:number;memoryUsed:number;memoryTotal:number};autostart?:boolean;
  clipboard:ClipboardEntry[];clipboardPaused:boolean;
  media:{available:boolean;title?:string;artist?:string;app?:string;status?:string;position?:number;duration?:number;start?:number;rate?:number;observedAt?:number;controls?:{play:boolean;pause:boolean;previous:boolean;next:boolean;seek?:boolean}};
  lyrics?:LyricsSnapshot;
  battery:{available:boolean;percent?:number;status?:number};
  drives?:string[];events:DesktopEvent[];
  weather:null|{city:string;region?:string;temperature_2m?:number;apparent_temperature?:number;relative_humidity_2m?:number;weather_code?:number;wind_speed_10m?:number;high?:number;low?:number;at:number};
  city:string;inbox:string;
};
export type ReasoningEffort = 'auto'|'low'|'medium'|'high';
export type LocalService={label:string;endpoint:string;port:string;builtin:boolean;running:boolean;models:string[];note:string};
export type ModelProfileSnapshot = {id:string;name:string;endpoint:string;model:string;reasoningEffort?:ReasoningEffort;keyPresent:boolean};
export type ModelConfigSnapshot = {builtinEnabled?:boolean;allowRemoteAttachments?:boolean;endpoint:string;model:string;reasoningEffort?:ReasoningEffort;keyPresent:boolean;keyPersistent:boolean;secretUnavailable?:boolean;configUnavailable?:boolean;profiles?:ModelProfileSnapshot[]};
export type ModelConnectionTest = {endpoint:string;models:string[];listingAvailable:boolean;keyVerified:boolean;modelListed?:boolean|null;message:string};
export type TranslationConfigSnapshot = {mode:'system'|'custom';provider:'local'|'cloud';endpoint:string;model:string;reasoningEffort?:ReasoningEffort;keyPresent:boolean};
export type TranslationSnapshot={enabled:boolean;phase:string;source:string;text:string;error:string;target:string;method:string};

export type AttachmentMode='both'|'text'|'image';
export type StoredAttachment={id:string;name:string;size:number;kind:'image'|'document';characters?:number};
export type ConversationTurn={id:string;role:'user'|'assistant';content:string;attachments?:string[];files?:StoredAttachment[]};
export type ChatSession={id:string;title:string;updatedAt:number;count:number};
export type ConversationSnapshot={persistence:boolean;activeId:string;sessions:ChatSession[];messages:ConversationTurn[]};
export type ChatAttachment={id:string;name:string;size:number;kind:'image'|'document';preview?:string;truncated:boolean;characters?:number;recognition?:'ocr';imageMode?:AttachmentMode};
export type AttachmentReviewItem={id:string;name:string;size:number;kind:'image'|'document';imagePreview?:string;characters?:number;truncated:boolean;imageMode?:AttachmentMode;imageIncluded:boolean;textIncluded:boolean;textPreview:string};
export type AttachmentReview={reviewId:string;endpoint:string;endpointHost:string;model:string;remote:boolean;authorized:boolean;items:AttachmentReviewItem[]};

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
  aiAttachMode?(id:string,mode:AttachmentMode):Promise<{id:string;imageMode:AttachmentMode}>;
  aiAttachmentReview?(ids:string[],model:string):Promise<AttachmentReview>;
  aiAttachmentApprove?(reviewId:string,ids:string[],model:string):Promise<{ticket:string}>;
  conversations?():Promise<ConversationSnapshot>;
  conversationStore?(payload:{id:string;messages:ConversationTurn[]}):Promise<ConversationSnapshot>;
  conversationNew?():Promise<ConversationSnapshot>;
  conversationOpen?(id:string):Promise<ConversationSnapshot>;
  conversationRename?(id:string,title:string):Promise<ConversationSnapshot>;
  conversationDelete?(id:string):Promise<ConversationSnapshot>;
  conversationsClear?():Promise<ConversationSnapshot>;
  conversationsPersistence?(enabled:boolean):Promise<ConversationSnapshot>;
  aiModels?(): Promise<{endpoint:string;models:string[];preferredModel?:string}>;
  aiChat?(payload: {id:string;model:string;messages:{role:'user'|'assistant';content:string;attachments?:string[]}[];attachmentApproval?:string}): Promise<{text:string}>;
  aiCancel?(): Promise<void>;
  aiSubscribe?(listener:(update:{id:string;phase:string;text:string})=>void):()=>void;
  openExternal?(url:string):Promise<void>;
  desktopSnapshot?():Promise<DesktopSnapshot>;
  desktopAction?(input:{name:string;value?:unknown}):Promise<DesktopSnapshot>;
  desktopSubscribe?(listener:(event:DesktopEvent)=>void):()=>void;
  clipboardRead?(id:string):Promise<string>;
  workbenchTimers?():Promise<TimersSnapshot>;
  workbenchTimersSet?(patch:{focus?:Partial<TimersFocus>;todos?:TimersTodo[];health?:Partial<TimersHealth>}):Promise<TimersSnapshot>;
  workbenchTimersSubscribe?(listener:(value:TimersSnapshot)=>void):()=>void;
  builtinModelSet?(enabled:boolean):Promise<ModelConfigSnapshot>;
  modelDiscover?():Promise<LocalService[]>;
  modelConfig?():Promise<ModelConfigSnapshot>;
  modelConfigSet?(input:{endpoint:string;model:string;reasoningEffort?:ReasoningEffort;apiKey?:string;clearKey?:boolean}):Promise<ModelConfigSnapshot>;
  modelTest?(input:{endpoint:string;model:string;apiKey?:string}):Promise<ModelConnectionTest>;
  modelProfileSave?(input:{id?:string;name:string;endpoint:string;model:string;reasoningEffort?:ReasoningEffort;apiKey?:string;clearKey?:boolean;includeApiKey?:boolean}):Promise<ModelConfigSnapshot>;
  modelProfileUse?(id:string):Promise<ModelConfigSnapshot>;
  modelProfileDelete?(id:string):Promise<ModelConfigSnapshot>;
  modelAttachmentsSet?(enabled:boolean):Promise<ModelConfigSnapshot>;
  translationConfig?():Promise<TranslationConfigSnapshot>;
  translationConfigSet?(input:{mode:'system'|'custom';provider:'local'|'cloud';endpoint:string;model:string;reasoningEffort?:ReasoningEffort;apiKey?:string;clearKey?:boolean}):Promise<TranslationConfigSnapshot>;
}
export type WorkbenchConfig={theme:'light'|'mist'|'dark';reduced:boolean;particles:boolean;buttonHints:boolean;bubble:'light'|'mist'|'dark';persona:string;memory:string;shortcuts:Record<string,string>;shortcutStatus?:Record<string,string>};
// Focus, todos and health reminders live in the main process; these are the shapes it owns.
export type TimersFocus={end:number|null;remaining:number;duration:number;breakDuration:number;completed:number;mode:'focus'|'break'};
export type TimersTodo={id:string;text:string;due:string;done:boolean;notified?:boolean};
export type TimersHealth={enabled:boolean;minutes:number;next:number};
export type TimersSnapshot={focus:TimersFocus;todos:TimersTodo[];health:TimersHealth;serverTime:number};

declare global {
  interface Window { yukiHost?: DesktopHost }
}
