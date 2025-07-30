import { Injectable } from '@nestjs/common';
import axios from 'axios';

@Injectable()
export class OcrService {
  async imageOcr(imageInBase64: string) {
    const ocrResponse = await axios.post('http://127.0.0.1:8000/ocr', {
      imageBase64: imageInBase64,
    });
    return ocrResponse.data;
  }
}
