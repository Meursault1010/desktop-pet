// Future input must be explicitly selected and user-started; migration does not capture audio.
export type AudioFeatures={volume:number;low:number;mid:number;high:number;beat:boolean};
export interface AudioFeatureSource {
  start(sourceId:string,signal:AbortSignal):AsyncIterable<AudioFeatures>;
  stop():void;
}
