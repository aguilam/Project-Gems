import { Injectable } from '@nestjs/common';
import axios from 'axios';

export interface FileDTO {
  buffer: string;
  name: string;
  mime: string;
}

@Injectable()
export class fileRecognizeService {
  async recognize(byteFile: FileDTO) {
    const fileResponse = await axios.post(
      'http://127.0.0.1:8000/files',
      byteFile,
    );
    const fullResponse = `Пользователь предоставил контекст в файлах, вот что в  них было. /n ${fileResponse.data}`;
    return fullResponse;
  }
}
