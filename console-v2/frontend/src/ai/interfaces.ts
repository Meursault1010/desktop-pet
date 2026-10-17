// Future adapters only. No remote provider, credentials, network or tool runner is installed.
export interface ConversationProvider {
  reply(text:string,signal:AbortSignal):AsyncIterable<string>;
}
export interface SpeechProvider {
  transcribe(input:Blob,signal:AbortSignal):Promise<string>;
  synthesize(text:string,signal:AbortSignal):Promise<Blob>;
}
