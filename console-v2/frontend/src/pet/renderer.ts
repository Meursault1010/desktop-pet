export type Clip = {id:string;atlas:string;frames:number;columns:number;cell:number;durations:number[];loop_start?:number;pixel_art?:boolean};
export interface PetRenderer {
  loadCharacter(id:string):Promise<void>;
  playAction(action:Clip,loop?:boolean,speed?:number):Promise<void>;
  stopAction():Promise<void>;
  setParameter(name:'opacity'|'scale',value:number):void;
  dispose():void;
}
// A future Live2D implementation must implement PetRenderer; no SDK or remote service is loaded.
