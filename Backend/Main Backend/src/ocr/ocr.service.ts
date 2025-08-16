import { Injectable } from '@nestjs/common';
import axios from 'axios';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class OcrService {
  constructor(private configService: ConfigService) {}

  async imageOcr(imageInBase64: string) {
    const ocrResponse = await axios.post(
      `${this.configService.get<string>('LLM_SERVER_URL')}/ocr`,
      {
        imageBase64: imageInBase64,
      },
    );
    const fullResponse = `Пользователь предоставил контекст в фото, вот что на них было. /n ${ocrResponse.data}`;
    return fullResponse;
  }
}
