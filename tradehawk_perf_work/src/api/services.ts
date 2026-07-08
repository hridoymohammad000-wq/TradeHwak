import { fetchControlSettings, saveControlSettings } from './client';
import { ControlCenterSettings, SettingsUpdatePayload, MarketTicker } from './types';
export async function getTickers():Promise<MarketTicker[]>{ return []; }
export function getSettings():Promise<ControlCenterSettings>{ return fetchControlSettings(); }
export function updateSettings(settings:ControlCenterSettings):Promise<ControlCenterSettings>{
 return saveControlSettings({scalping:settings.risk.scalping,intraday:settings.risk.intraday});
}
export function patchSettings(payload:SettingsUpdatePayload):Promise<ControlCenterSettings>{ return saveControlSettings(payload); }
