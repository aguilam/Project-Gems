import { Module } from '@nestjs/common';
import { usersController } from './users.controller';
import { UsersService } from './users.service';

@Module({
  exports: [],
  controllers: [usersController],
  providers: [UsersService],
})
export class UsersModule {}
