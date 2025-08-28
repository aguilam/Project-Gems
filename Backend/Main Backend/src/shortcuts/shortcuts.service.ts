import {
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

type PatchShortcutDto = {
  id: string;
  command?: string | null;
  modelId?: string | null;
  instruction?: string | null;
};
@Injectable()
export class ShortcutsService {
  constructor(private prismaService: PrismaService) {}

  async postNewShortcut(dto: {
    instruction: string;
    command: string;
    modelId: string;
    telegramId: string;
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
        telegramId: String(dto.telegramId),
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
  async getShortcutsByTelegramId(telegramId: string) {
    const user = await this.prismaService.user.findUnique({
      where: {
        telegramId: String(telegramId),
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
  async patchShortcutById(dto: PatchShortcutDto) {
    const data: Record<string, any> = {};
    if (dto.command !== undefined) {
      if (dto.command === null) {
        data.command = null;
      } else {
        if (dto.command.length < 2) throw new Error('Команда слишком короткая');
        const exists = await this.prismaService.shortcut.findFirst({
          where: { command: dto.command, NOT: { id: dto.id } },
        });
        if (exists) throw new Error('Команда уже используется');
        data.command = dto.command;
      }
    }

    if (dto.modelId !== undefined) {
      if (dto.modelId === null) {
        data.modelId = null;
      } else {
        const model = await this.prismaService.aIModel.findUnique({
          where: { id: dto.modelId },
        });
        if (!model) throw new Error('Указанная модель не найдена');
        data.modelId = dto.modelId;
      }
    }

    if (dto.instruction !== undefined) {
      if (dto.instruction === null) {
        data.instruction = null;
      } else {
        const instr = dto.instruction.trim();
        if (instr.length > 2000) throw new Error('Инструкция слишком длинная');
        data.instruction = instr;
      }
    }

    if (Object.keys(data).length === 0) {
      return await this.prismaService.shortcut.findUnique({
        where: { id: dto.id },
      });
    }

    const updated = await this.prismaService.shortcut.update({
      where: { id: dto.id },
      data,
    });

    return updated;
  }
}
