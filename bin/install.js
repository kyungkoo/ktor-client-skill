#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const packageRoot = path.resolve(__dirname, "..");
const skillName = "ktor-mobile-client";
const sourceDir = path.join(packageRoot, skillName);

function printUsage() {
  console.log(`Install the ${skillName} Codex skill.

Usage:
  npx ktor-mobile-client-skill [--target <skills-dir>] [--force] [--dry-run]

Options:
  --target <dir>  Install into a custom skills directory.
  --force         Replace an existing installed skill with the same name.
  --dry-run       Print the resolved install paths without copying files.
  --help          Show this help message.
`);
}

function parseArgs(argv) {
  const options = {
    force: false,
    dryRun: false,
    target: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--force") {
      options.force = true;
      continue;
    }
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (arg === "--help" || arg === "-h") {
      options.help = true;
      continue;
    }
    if (arg === "--target") {
      const value = argv[i + 1];
      if (!value) {
        throw new Error("--target requires a directory path");
      }
      options.target = value;
      i += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function resolveSkillsDir(target) {
  if (target) {
    return path.resolve(target);
  }

  const codexHome = process.env.CODEX_HOME
    ? path.resolve(process.env.CODEX_HOME)
    : path.join(os.homedir(), ".codex");
  return path.join(codexHome, "skills");
}

function ensureSourceExists() {
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Skill source directory not found: ${sourceDir}`);
  }
  if (!fs.existsSync(path.join(sourceDir, "SKILL.md"))) {
    throw new Error(`SKILL.md not found in source skill directory: ${sourceDir}`);
  }
}

function copySkill(source, destination, force) {
  if (fs.existsSync(destination)) {
    if (!force) {
      throw new Error(
        `Destination already exists: ${destination}\nRe-run with --force to replace it.`
      );
    }
    fs.rmSync(destination, { recursive: true, force: true });
  }

  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true });
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(String(error.message || error));
    console.error("");
    printUsage();
    process.exit(1);
  }

  if (options.help) {
    printUsage();
    process.exit(0);
  }

  ensureSourceExists();

  const skillsDir = resolveSkillsDir(options.target);
  const destinationDir = path.join(skillsDir, skillName);

  if (options.dryRun) {
    console.log(`Package root: ${packageRoot}`);
    console.log(`Source skill: ${sourceDir}`);
    console.log(`Install dir: ${destinationDir}`);
    process.exit(0);
  }

  copySkill(sourceDir, destinationDir, options.force);

  console.log(`Installed ${skillName} to ${destinationDir}`);
  console.log(`Use it with: $${skillName}`);
}

main();
