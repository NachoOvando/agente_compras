import rawConfig from '@shared/app-config.json';

export interface AppConfig {
  producto: string;
  preguntasDemo: string[];
}

// Fuente única compartida con el motor Python (engine/config.py lee el mismo JSON).
export const appConfig: AppConfig = rawConfig;
