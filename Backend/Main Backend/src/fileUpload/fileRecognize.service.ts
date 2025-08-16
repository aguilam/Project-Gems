import { Injectable } from '@nestjs/common';
import axios from 'axios';

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
  async recognize(byteFile: FileDTO): Promise<string> {
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
        'http://127.0.0.1:8000/files',
        byteFile,
        axiosConfig,
      );

      const { data } = resp;

      const { content, type } = data as RecognizeResponseDTO;
      if (type === 'pdf') {
        return `Пользователь предоставил контекст в pdf файле, вот что в ней было.\n${content}`;
      } else if (type === 'table') {
        return `Пользователь предоставил контекст в таблице, вот что в ней было.\n${content}`;
      } else if (type === 'audio') {
        return content;
      } else {
        return `Пользователь предоставил контекст в текстовых файлах, вот что в них было.\n${content}`;
      }
    } catch (err: any) {
      throw new Error(`Ошибка сервера распознавания файла: ${err}`);
    }
  }
}
