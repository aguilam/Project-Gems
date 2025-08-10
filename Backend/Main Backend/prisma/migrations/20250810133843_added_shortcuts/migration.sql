-- CreateTable
CREATE TABLE "Shortcut" (
    "id" TEXT NOT NULL,
    "instruction" TEXT NOT NULL,
    "command" TEXT NOT NULL,
    "modelId" TEXT NOT NULL,
    "userId" TEXT,

    CONSTRAINT "Shortcut_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Shortcut_id_key" ON "Shortcut"("id");

-- AddForeignKey
ALTER TABLE "Shortcut" ADD CONSTRAINT "Shortcut_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "AIModel"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Shortcut" ADD CONSTRAINT "Shortcut_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;
