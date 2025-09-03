import { Injectable } from '@nestjs/common';
import axios from 'axios';
import { ConfigService } from '@nestjs/config';
import { PostHog } from 'posthog-node';
export interface FileDTO {
  buffer: string;
  name: string;
  mime: string;
}

export interface RecognizeResponseDTO {
  content: string;
  type: string;
}

@Injectable()
export class FileRecognizeService {
  constructor(private configService: ConfigService) {}
  async recognize(byteFile: FileDTO): Promise<{ text: string; type: string }> {
    try {
      const axiosConfig = {
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: 30_000,
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      };

      const resp = await axios.post<RecognizeResponseDTO>(
        `${this.configService.get<string>('LLM_SERVER_URL')}/files`,
        byteFile,
        axiosConfig,
      );

      const { data } = resp;

      const { content, type } = data as RecognizeResponseDTO;
      let text = '';
      if (type === 'pdf') {
        text = `Пользователь предоставил контекст в pdf файле, вот что в ней было.\n${content}`;
      } else if (type === 'table') {
        text = `Пользователь предоставил контекст в таблице, вот что в ней было.\n${content}`;
      } else if (type === 'audio') {
        text = content;
      } else {
        text = `Пользователь предоставил контекст в текстовых файлах, вот что в них было.\n${content}`;
      }
      return { text: text, type: type };
    } catch (err: any) {
      throw new Error(`Ошибка сервера распознавания файла: ${err}`);
    }
  }
}
