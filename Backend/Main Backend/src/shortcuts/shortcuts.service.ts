import { ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';
@Injectable()
export class ShortcutsService {
  constructor(private prismaService: PrismaService) {}

  async postNewShortcut(dto: {
    instruction: string;
    command: string;
    modelId: string;
    telegramId: number;
  }) {
    const forbiddenNames = ['/start', '/chats', '/roles'];

    forbiddenNames.forEach((name) => {
      if (name == dto.command) {
        throw new ForbiddenException(
          'Использовано не валидное имя для команды',
        );
      }
    });
    const user = await this.prismaService.user.findUnique({
      where: {
        telegramId: dto.telegramId,
      },
    });

    if (user) {
      const shortcuts = await this.prismaService.shortcut.findMany({
        where: {
          userId: user.id,
        },
      });
      shortcuts.forEach((shortcut) => {
        if (shortcut.command == dto.command) {
          throw new ForbiddenException('Данное имя команды занято');
        }
      });
      const shortcut = await this.prismaService.shortcut.create({
        data: {
          instruction: dto.instruction,
          command: dto.command,
          modelId: dto.modelId,
          userId: user.id,
        },
      });
      return shortcut;
    }
  }
  async getShortcutsByTelegramId(telegramId: number) {
    const user = await this.prismaService.user.findUnique({
      where: {
        telegramId: telegramId,
      },
    });
    if (user) {
      const shortcuts = await this.prismaService.shortcut.findMany({
        where: {
          userId: user?.id,
        },
      });
      return shortcuts;
    }
  }

  async deleteShortcutsById(id: string) {
    await this.prismaService.shortcut.delete({
      where: {
        id: id,
      },
    });
  }

  async getShortcutById(id: string) {
    const shortcut = await this.prismaService.shortcut.findUnique({
      where: {
        id: id,
      },
      include: {
        model: true,
      },
    });
    if (!shortcut) {
      throw new NotFoundException(`Shortcut with id ${id} not found`);
    }
    return shortcut;
  }

  async patchShortcutById(dto: {
    id: string;
    command: string;
    modelId: string;
    instruction: string;
  }) {
    await this.prismaService.shortcut.update({
      where: {
        id: dto.id,
      },
      data: {
        command: dto.command,
        modelId: dto.modelId,
        instruction: dto.instruction,
      },
    });
  }
}
