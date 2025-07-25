/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

export class Chat {
  id: number;
  title?: string;
}

@Injectable()
export class ModelsService {
  constructor(private prisma: PrismaService) {}

  async getAllModels() {
    const models = await this.prisma.aIModel.findMany();
    return models;
  }
}
