/*
  Warnings:

  - Made the column `userId` on table `Shortcut` required. This step will fail if there are existing NULL values in that column.

*/
-- DropForeignKey
ALTER TABLE "Shortcut" DROP CONSTRAINT "Shortcut_userId_fkey";

-- AlterTable
ALTER TABLE "Shortcut" ALTER COLUMN "userId" SET NOT NULL;

-- AlterTable
ALTER TABLE "User" ALTER COLUMN "telegramId" SET DATA TYPE TEXT;

-- AddForeignKey
ALTER TABLE "Shortcut" ADD CONSTRAINT "Shortcut_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
