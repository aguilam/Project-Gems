import { Injectable } from '@nestjs/common';
import axios from 'axios';

export interface FileDTO {
  buffer: string;
  name: string;
  mime: string;
}

export interface RecognizeResponseDTO {
  text: string;
  type: string;
}

@Injectable()
export class fileRecognizeService {
  async recognize(byteFile: FileDTO) {
    const fileResponse = await axios.post<RecognizeResponseDTO>(
      'http://127.0.0.1:8000/files',
      byteFile,
    );
    const { text, type } = fileResponse.data;
    if (type == 'pdf') {
      return `Пользователь предоставил контекст в pdf файле, вот что в  ней было. \n ${text}`;
    } else if (type == 'table') {
      return `Пользователь предоставил контекст в таблице, вот что в  ней было. \n ${text}`;
    } else if (type == 'audio') {
      return text;
    } else {
      return `Пользователь предоставил контекст в текстовых файлах, вот что в  них было. \n ${text}`;
    }
  }
}
