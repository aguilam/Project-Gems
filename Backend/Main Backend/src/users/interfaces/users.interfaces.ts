export interface User {
  id: number;
  telegramId: string;
  userName: string;
  systemPrompt: string;
  defaultModel: string;
  premium: boolean;
  freeQuestion: number;
  premiumQuestion: number;
}
