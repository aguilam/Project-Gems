export interface User {
  id: number;
  telegramId: number;
  userName: string;
  systemPrompt: string;
  defaultModel: string;
  premium: boolean;
  freeQuestion: number;
  premiumQuestion: number;
}
