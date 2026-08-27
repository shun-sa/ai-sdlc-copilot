#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const childProcess = require("child_process");

function loadTypeScript(repoRoot) {
  const candidates = [repoRoot, process.cwd(), __dirname];
  for (const candidate of candidates) {
    try {
      return require(require.resolve("typescript", { paths: [candidate] }));
    } catch (_) {}
  }
  try {
    const globalRoot = childProcess.execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
    return require(path.join(globalRoot, "typescript"));
  } catch (_) {
    throw new Error("TypeScript Compiler API is unavailable. Install the project's TypeScript dependency or make it resolvable by Node.js.");
  }
}

function normalizeRel(repoRoot, filePath) {
  return path.relative(repoRoot, path.resolve(filePath)).split(path.sep).join("/");
}

function moduleName(repoRoot, filePath) {
  let rel = normalizeRel(repoRoot, filePath).replace(/\.(tsx?|jsx?)$/i, "");
  rel = rel.replace(/\/index$/i, "");
  return rel.split("/").filter(Boolean).join(".");
}

function resolveImportModule(repoRoot, sourceFile, specifier) {
  if (!specifier.startsWith(".")) return specifier.replace(/\//g, ".");
  const base = path.resolve(path.dirname(sourceFile), specifier);
  let rel = path.relative(repoRoot, base).split(path.sep).join("/");
  rel = rel.replace(/\.(tsx?|jsx?)$/i, "").replace(/\/index$/i, "");
  return rel.split("/").filter(Boolean).join(".");
}

function emit(record) {
  process.stdout.write(JSON.stringify(record) + "\n");
}

function main() {
  if (process.argv.length < 4) {
    console.error("Usage: node typescript_ast_analyzer.cjs <repo-root> <files...>");
    process.exit(2);
  }

  const repoRoot = path.resolve(process.argv[2]);
  const files = process.argv.slice(3).map((item) => path.resolve(item));
  const ts = loadTypeScript(repoRoot);

  for (const filePath of files) {
    const text = fs.readFileSync(filePath, "utf8");
    const scriptKind = filePath.endsWith(".tsx") ? ts.ScriptKind.TSX
      : filePath.endsWith(".ts") ? ts.ScriptKind.TS
      : filePath.endsWith(".jsx") ? ts.ScriptKind.JSX
      : ts.ScriptKind.JS;
    const sf = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, scriptKind);
    const mod = moduleName(repoRoot, filePath);
    const rel = normalizeRel(repoRoot, filePath);

    const importedSymbols = new Map();
    const importedNamespaces = new Map();
    const classStack = [];

    for (const statement of sf.statements) {
      if (!ts.isImportDeclaration(statement) || !statement.importClause || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
      const importedModule = resolveImportModule(repoRoot, filePath, statement.moduleSpecifier.text);
      const clause = statement.importClause;
      if (clause.name) importedSymbols.set(clause.name.text, `${importedModule}.${clause.name.text}`);
      if (clause.namedBindings) {
        if (ts.isNamespaceImport(clause.namedBindings)) {
          importedNamespaces.set(clause.namedBindings.name.text, importedModule);
        } else if (ts.isNamedImports(clause.namedBindings)) {
          for (const element of clause.namedBindings.elements) {
            const sourceName = element.propertyName ? element.propertyName.text : element.name.text;
            importedSymbols.set(element.name.text, `${importedModule}.${sourceName}`);
          }
        }
      }
    }

    function lineOf(node) {
      return sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
    }

    function currentClassQn() {
      if (!classStack.length) return null;
      return [mod, ...classStack].filter(Boolean).join(".");
    }

    function analyzeFunction(node, symbol, qualified, kind) {
      const variableTypes = new Map();
      const calls = [];
      let assertionCount = 0;

      function resolveClassName(name) {
        if (importedSymbols.has(name)) return importedSymbols.get(name);
        return [mod, name].filter(Boolean).join(".");
      }

      function rawText(expr) {
        return expr.getText(sf);
      }

      function resolveCall(expr) {
        if (ts.isIdentifier(expr)) {
          if (importedSymbols.has(expr.text)) return importedSymbols.get(expr.text);
          const classQn = currentClassQn();
          return classQn ? `${classQn}.${expr.text}` : [mod, expr.text].filter(Boolean).join(".");
        }
        if (!ts.isPropertyAccessExpression(expr)) return null;
        const method = expr.name.text;
        const base = expr.expression;
        if (ts.isThis(base)) {
          const classQn = currentClassQn();
          return classQn ? `${classQn}.${method}` : null;
        }
        if (ts.isIdentifier(base)) {
          if (variableTypes.has(base.text)) return `${variableTypes.get(base.text)}.${method}`;
          if (importedNamespaces.has(base.text)) return `${importedNamespaces.get(base.text)}.${method}`;
          if (importedSymbols.has(base.text)) return `${importedSymbols.get(base.text)}.${method}`;
        }
        if (ts.isNewExpression(base) && ts.isIdentifier(base.expression)) {
          return `${resolveClassName(base.expression.text)}.${method}`;
        }
        return null;
      }

      function assertionLike(expr) {
        const raw = rawText(expr).toLowerCase();
        if (ts.isIdentifier(expr)) {
          return expr.text.startsWith("assert") || expr.text === "fail";
        }
        if (ts.isPropertyAccessExpression(expr)) {
          const name = expr.name.text.toLowerCase();
          return name.startsWith("assert") || name.startsWith("to") || raw.includes("assert.") || raw.includes("expect(");
        }
        return false;
      }

      function visit(child) {
        if (ts.isVariableDeclaration(child) && ts.isIdentifier(child.name)) {
          if (child.initializer && ts.isNewExpression(child.initializer) && ts.isIdentifier(child.initializer.expression)) {
            variableTypes.set(child.name.text, resolveClassName(child.initializer.expression.text));
          } else if (child.type && ts.isTypeReferenceNode(child.type) && ts.isIdentifier(child.type.typeName)) {
            variableTypes.set(child.name.text, resolveClassName(child.type.typeName.text));
          }
        }
        if (ts.isCallExpression(child)) {
          const raw = rawText(child.expression);
          const qn = resolveCall(child.expression);
          const call = { raw, line: lineOf(child) };
          if (qn) call.qualified_name = qn;
          calls.push(call);
          if (assertionLike(child.expression)) assertionCount += 1;
        }
        if (ts.isBinaryExpression(child)) {
          const op = child.operatorToken.kind;
          if ([ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(op)) {
            // Comparison alone is not an assertion. Do not count it.
          }
        }
        ts.forEachChild(child, visit);
      }

      if (node.body) ts.forEachChild(node.body, visit);
      emit({
        language: "typescript",
        file: rel,
        kind,
        symbol,
        qualified_name: qualified,
        line: lineOf(node),
        calls,
        assertion_count: assertionCount,
      });
    }

    function scan(node) {
      if (ts.isClassDeclaration(node) && node.name) {
        const name = node.name.text;
        classStack.push(name);
        emit({
          language: "typescript",
          file: rel,
          kind: "class",
          symbol: name,
          qualified_name: [mod, ...classStack].filter(Boolean).join("."),
          line: lineOf(node),
          calls: [],
          assertion_count: 0,
        });
        for (const member of node.members) {
          if (ts.isMethodDeclaration(member) && member.name) {
            const method = member.name.getText(sf).replace(/["']/g, "");
            analyzeFunction(member, method, `${currentClassQn()}.${method}`, "method");
          }
        }
        // Process nested declarations without re-processing methods.
        for (const member of node.members) {
          if (!ts.isMethodDeclaration(member)) ts.forEachChild(member, scan);
        }
        classStack.pop();
        return;
      }
      if (ts.isFunctionDeclaration(node) && node.name) {
        const name = node.name.text;
        analyzeFunction(node, name, [mod, name].filter(Boolean).join("."), "function");
        return;
      }
      if (ts.isVariableStatement(node)) {
        for (const declaration of node.declarationList.declarations) {
          if (ts.isIdentifier(declaration.name) && declaration.initializer && (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer))) {
            const name = declaration.name.text;
            analyzeFunction(declaration.initializer, name, [mod, name].filter(Boolean).join("."), "function");
          }
        }
      }
      ts.forEachChild(node, scan);
    }

    scan(sf);
  }
}

try {
  main();
} catch (error) {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
}
