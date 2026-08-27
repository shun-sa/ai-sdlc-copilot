import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;
import javax.lang.model.element.Modifier;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

import com.sun.source.tree.AssertTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.NewClassTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.VariableTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePathScanner;

/**
 * Lightweight Java source AST analyzer using only the JDK Compiler Tree API.
 *
 * It parses source without compiling project dependencies. Symbol/call resolution
 * is therefore intentionally syntactic and conservative: it resolves imports,
 * current-class calls, static-class calls, and variables whose declared/new type
 * can be identified. Unresolvable calls remain raw rather than being guessed.
 */
public class JavaAstAnalyzer {
    private static final class Call {
        String raw;
        String qualified;
        long line;
        Call(String raw, String qualified, long line) {
            this.raw = raw;
            this.qualified = qualified;
            this.line = line;
        }
    }

    private static final class Symbol {
        String file;
        String kind;
        String symbol;
        String qualified;
        long line;
        List<Call> calls = new ArrayList<>();
        int assertions = 0;
    }

    private static String escape(String value) {
        if (value == null) return "";
        StringBuilder out = new StringBuilder();
        for (char c : value.toCharArray()) {
            switch (c) {
                case '\\': out.append("\\\\"); break;
                case '"': out.append("\\\""); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default: out.append(c);
            }
        }
        return out.toString();
    }

    private static String json(Symbol s) {
        StringBuilder out = new StringBuilder();
        out.append("{");
        out.append("\"language\":\"java\",");
        out.append("\"file\":\"").append(escape(s.file)).append("\",");
        out.append("\"kind\":\"").append(escape(s.kind)).append("\",");
        out.append("\"symbol\":\"").append(escape(s.symbol)).append("\",");
        out.append("\"qualified_name\":\"").append(escape(s.qualified)).append("\",");
        out.append("\"line\":").append(s.line).append(",");
        out.append("\"assertion_count\":").append(s.assertions).append(",");
        out.append("\"calls\":[");
        for (int i = 0; i < s.calls.size(); i++) {
            if (i > 0) out.append(",");
            Call c = s.calls.get(i);
            out.append("{");
            out.append("\"raw\":\"").append(escape(c.raw)).append("\"");
            if (c.qualified != null && !c.qualified.isBlank()) {
                out.append(",\"qualified_name\":\"").append(escape(c.qualified)).append("\"");
            }
            out.append(",\"line\":").append(c.line);
            out.append("}");
        }
        out.append("]}");
        return out.toString();
    }

    private static final class Scanner extends TreePathScanner<Void, Void> {
        final CompilationUnitTree unit;
        final Path repoRoot;
        final String relFile;
        final String packageName;
        final Map<String, String> importedTypes = new HashMap<>();
        final Map<String, String> staticImports = new HashMap<>();
        final Deque<String> classStack = new ArrayDeque<>();
        final List<Symbol> symbols = new ArrayList<>();
        Symbol currentMethod = null;
        Map<String, String> variableTypes = new HashMap<>();

        Scanner(CompilationUnitTree unit, Path repoRoot) {
            this.unit = unit;
            this.repoRoot = repoRoot;
            Path sourcePath = Paths.get(unit.getSourceFile().toUri()).toAbsolutePath().normalize();
            String rel;
            try {
                rel = repoRoot.relativize(sourcePath).toString();
            } catch (IllegalArgumentException ex) {
                rel = sourcePath.toString();
            }
            this.relFile = rel.replace('\\', '/');
            this.packageName = unit.getPackageName() == null ? "" : unit.getPackageName().toString();
            collectImports();
        }

        void collectImports() {
            for (ImportTree item : unit.getImports()) {
                String imported = item.getQualifiedIdentifier().toString();
                if (item.isStatic()) {
                    if (!imported.endsWith(".*")) {
                        int dot = imported.lastIndexOf('.');
                        if (dot > 0) {
                            staticImports.put(imported.substring(dot + 1), imported);
                        }
                    }
                    continue;
                }
                if (!imported.endsWith(".*")) {
                    int dot = imported.lastIndexOf('.');
                    String simple = dot >= 0 ? imported.substring(dot + 1) : imported;
                    importedTypes.put(simple, imported);
                }
            }
        }

        long line(Tree tree) {
            long position = com.sun.source.util.Trees.instance(task).getSourcePositions().getStartPosition(unit, tree);
            if (position < 0 || unit.getLineMap() == null) return -1;
            return unit.getLineMap().getLineNumber(position);
        }

        String currentClassQn() {
            if (classStack.isEmpty()) return null;
            List<String> names = new ArrayList<>(classStack);
            java.util.Collections.reverse(names);
            String joined = String.join(".", names);
            return packageName.isBlank() ? joined : packageName + "." + joined;
        }

        String resolveType(String raw) {
            if (raw == null || raw.isBlank()) return null;
            String clean = raw.replaceAll("<.*>", "").replace("[]", "").trim();
            if (clean.contains(".")) return clean;
            if (importedTypes.containsKey(clean)) return importedTypes.get(clean);
            if (!packageName.isBlank()) return packageName + "." + clean;
            return clean;
        }

        @Override
        public Void visitClass(ClassTree node, Void unused) {
            String name = node.getSimpleName().toString();
            classStack.push(name);
            Symbol s = new Symbol();
            s.file = relFile;
            s.kind = "class";
            s.symbol = name;
            s.qualified = currentClassQn();
            s.line = line(node);
            symbols.add(s);
            super.visitClass(node, unused);
            classStack.pop();
            return null;
        }

        @Override
        public Void visitMethod(MethodTree node, Void unused) {
            Symbol previousMethod = currentMethod;
            Map<String, String> previousVariables = variableTypes;
            variableTypes = new HashMap<>();

            Symbol s = new Symbol();
            s.file = relFile;
            String methodName = node.getName().toString();
            boolean constructor = methodName.equals("<init>");
            s.kind = constructor ? "constructor" : "method";
            if (constructor) {
                methodName = classStack.isEmpty() ? "constructor" : classStack.peek();
            }
            s.symbol = methodName;
            String classQn = currentClassQn();
            s.qualified = classQn == null ? methodName : classQn + "." + methodName;
            s.line = line(node);
            symbols.add(s);
            currentMethod = s;

            for (VariableTree parameter : node.getParameters()) {
                variableTypes.put(parameter.getName().toString(), resolveType(parameter.getType().toString()));
            }

            super.visitMethod(node, unused);
            currentMethod = previousMethod;
            variableTypes = previousVariables;
            return null;
        }

        @Override
        public Void visitVariable(VariableTree node, Void unused) {
            if (currentMethod != null) {
                String type = resolveType(node.getType() == null ? "" : node.getType().toString());
                if (node.getInitializer() instanceof NewClassTree) {
                    NewClassTree newClass = (NewClassTree) node.getInitializer();
                    type = resolveType(newClass.getIdentifier().toString());
                }
                if (type != null && !type.isBlank()) {
                    variableTypes.put(node.getName().toString(), type);
                }
            }
            return super.visitVariable(node, unused);
        }

        String methodName(Tree select) {
            if (select instanceof IdentifierTree) {
                return ((IdentifierTree) select).getName().toString();
            }
            if (select instanceof MemberSelectTree) {
                return ((MemberSelectTree) select).getIdentifier().toString();
            }
            return select.toString();
        }

        String resolveCall(Tree select) {
            if (select instanceof IdentifierTree) {
                String name = ((IdentifierTree) select).getName().toString();
                if (staticImports.containsKey(name)) return staticImports.get(name);
                String classQn = currentClassQn();
                return classQn == null ? null : classQn + "." + name;
            }
            if (!(select instanceof MemberSelectTree)) return null;
            MemberSelectTree member = (MemberSelectTree) select;
            String method = member.getIdentifier().toString();
            Tree expression = member.getExpression();
            String expr = expression.toString();

            if (expr.equals("this") || expr.equals("super")) {
                String classQn = currentClassQn();
                return classQn == null ? null : classQn + "." + method;
            }
            if (variableTypes.containsKey(expr)) {
                return variableTypes.get(expr) + "." + method;
            }
            if (importedTypes.containsKey(expr)) {
                return importedTypes.get(expr) + "." + method;
            }
            if (expression instanceof NewClassTree) {
                String type = resolveType(((NewClassTree) expression).getIdentifier().toString());
                return type == null ? null : type + "." + method;
            }
            return null;
        }

        boolean looksLikeAssertion(MethodInvocationTree node) {
            String raw = node.getMethodSelect().toString();
            String name = methodName(node.getMethodSelect());
            String lower = raw.toLowerCase();
            return name.startsWith("assert")
                    || lower.contains("assertions.assert")
                    || lower.contains("assertthat")
                    || name.equals("fail")
                    || lower.contains("verify(")
                    || lower.startsWith("verify");
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree node, Void unused) {
            if (currentMethod != null) {
                currentMethod.calls.add(
                    new Call(node.getMethodSelect().toString(), resolveCall(node.getMethodSelect()), line(node))
                );
                if (looksLikeAssertion(node)) currentMethod.assertions += 1;
            }
            return super.visitMethodInvocation(node, unused);
        }

        @Override
        public Void visitAssert(AssertTree node, Void unused) {
            if (currentMethod != null) currentMethod.assertions += 1;
            return super.visitAssert(node, unused);
        }
    }

    private static JavacTask task;

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: java JavaAstAnalyzer.java <repo-root> <java-files...>");
            System.exit(2);
        }

        Path repoRoot = Paths.get(args[0]).toAbsolutePath().normalize();
        List<String> fileNames = new ArrayList<>();
        for (int i = 1; i < args.length; i++) fileNames.add(args[i]);

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            System.err.println("JDK compiler is not available. A JDK, not a JRE, is required.");
            System.exit(3);
        }

        try (StandardJavaFileManager fileManager = compiler.getStandardFileManager(null, null, null)) {
            Iterable<? extends JavaFileObject> units = fileManager.getJavaFileObjectsFromStrings(fileNames);
            task = (JavacTask) compiler.getTask(null, fileManager, null, List.of("-proc:none"), null, units);
            Iterable<? extends CompilationUnitTree> parsed = task.parse();
            for (CompilationUnitTree unit : parsed) {
                Scanner scanner = new Scanner(unit, repoRoot);
                scanner.scan(unit, null);
                for (Symbol symbol : scanner.symbols) {
                    System.out.println(json(symbol));
                }
            }
        }
    }
}
