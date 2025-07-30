import { json } from 'express';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { NestExpressApplication } from '@nestjs/platform-express';

async function bootstrap() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule);

  app.use('/messages', json({ limit: '20mb' }));
  app.useBodyParser('json', { limit: '100kb' });

  await app.listen(3000);
}
bootstrap();
