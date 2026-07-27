"""
Dependency parsers for various programming languages.
"""

from pathlib import Path
from typing import List, Optional, Dict
import os
import re


class BaseParser:
    """Base class for dependency parsers."""

    # Subclasses should override these
    LANGUAGE_NAME = "base"
    EXTENSIONS = []

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """
        Parse dependencies from a file.

        Returns:
            List of dependency module paths (raw strings from imports)
        """
        raise NotImplementedError


class PythonParser(BaseParser):
    """Parser for Python files."""

    LANGUAGE_NAME = "python"
    EXTENSIONS = ['.py']

    # Regex patterns for Python imports - handle both absolute and relative imports
    IMPORT_PATTERN = re.compile(r'^(?:from|import)\s+([\.A-Za-z_][\.A-Za-z0-9_\.]*)', re.MULTILINE)

    # Known external packages that are definitely not local
    EXTERNAL_PACKAGES = {
        'sys', 'os', 'io', 're', 'time', 'datetime', 'json', 'math',
        'collections', 'itertools', 'functools', 'operator',
        'pickle', 'shelve', 'sqlite3', 'csv', 'configparser',
        'hashlib', 'hmac', 'secrets', 'ssl', 'socket',
        'urllib', 'http', 'ftplib', 'smtplib', 'poplib', 'imaplib',
        'email', 'html', 'xml', 'tkinter', 'threading', 'multiprocessing',
        'subprocess', 'asyncio', 'typing', 'warnings', 'logging',
        'unittest', 'doctest', 'traceback', 'gc', 'weakref',
        'types', 'dis', 'inspect', 'code', 'ast', 'platform',
        'errno', 'ctypes', 'struct', 'array', 'copy', 'pprint',
        'textwrap', 'string', 'difflib', 'spwd', 'grp', 'pwd',
        'termios', 'tty', 'pty', 'fcntl', 'resource', 'getopt',
        'optparse', 'argparse', 'tempfile', 'shutil', 'glob',
        'fnmatch', 'linecache', 'tokenize', 'keyword', 'token',
        'tabnanny', 'purge', 'pyclbr', 'py_compile', 'compileall',
        'distutils', 'site', 'venv', 'ensurepip', 'zipapp', 'zipfile',
        'tarfile', 'gzip', 'bz2', 'lzma', 'zipimport', 'pkgutil',
        'modulefinder', 'runpy', 'importlib', 'builtins',
        # Third-party packages
        'numpy', 'pandas', 'scipy', 'matplotlib', 'sklearn',
        'tensorflow', 'torch', 'keras', 'flask', 'django', 'fastapi',
        'requests', 'urllib3', 'aiohttp', 'httpx', 'websocket',
        'pytest', 'nose', 'coverage', 'tox', 'pip', 'setuptools',
        'PIL', 'cv2', 'opencv', 'yaml', 'toml', 'certifi',
        'boto3', 'botocore', 'redis', 'pymongo', 'mysql', 'psycopg2',
        'grpc', 'protobuf', 'twisted', 'kafka', 'rabbitmq',
        'pandas', 'polars', 'dask', 'modin',
    }

    # Relative import markers - definitely local
    RELATIVE_MARKERS = {'.'}

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse Python import statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except IOError:
                return []

        deps = []

        # Match: import xxx, from xxx import yyy, from .xxx import yyy
        for match in self.IMPORT_PATTERN.finditer(content):
            module = match.group(1)
            first_module = module.split('.')[0]
            
            # Rule 1: Relative imports (. or ..) - definitely local
            if first_module in self.RELATIVE_MARKERS:
                deps.append(module)
                continue
            
            # Rule 2: Known external packages - skip
            if first_module.lower() in self.EXTERNAL_PACKAGES:
                continue
            
            # Rule 3: Unknown module - include for later path resolution
            deps.append(module)

        return deps

    def is_external(self, module: str) -> bool:
        """Check if module is definitely external."""
        first_module = module.split('.')[0]
        return first_module.lower() in self.EXTERNAL_PACKAGES


class JavaParser(BaseParser):
    """Parser for Java files."""

    LANGUAGE_NAME = "java"
    EXTENSIONS = ['.java']

    # Regex for Java imports
    IMPORT_PATTERN = re.compile(r'^import\s+([A-Za-z_][A-Za-z0-9_\.]*)\s*;', re.MULTILINE)

    # Known external packages
    EXTERNAL_PACKAGES = {
        'java.lang', 'java.util', 'java.io', 'java.nio', 'java.math',
        'java.text', 'java.time', 'java.net', 'java.security',
        'java.sql', 'java.xml', 'java.rmi', 'java.management',
        'java.beans', 'java.applet', 'java.awt', 'javax.swing',
        'sun.', 'com.sun', 'org.sun',
        'org.junit', 'org.mockito', 'org.powermock',
        'org.springframework', 'org.hibernate', 'org.apache',
        'com.google', 'com.fasterxml', 'io.netty', 'reactor',
    }

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse Java import statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return []

        deps = []
        for match in self.IMPORT_PATTERN.finditer(content):
            package = match.group(1)
            if not self._is_external(package):
                deps.append(package)

        return deps

    def _is_external(self, package: str) -> bool:
        """Check if package is external."""
        for external in self.EXTERNAL_PACKAGES:
            if package.startswith(external):
                return True
        return False


class JavaScriptParser(BaseParser):
    """Parser for JavaScript/TypeScript files."""

    LANGUAGE_NAME = "javascript"
    EXTENSIONS = ['.js', '.jsx', '.mjs', '.cjs']

    # Regex patterns for JS imports
    IMPORT_FROM_PATTERN = re.compile(
        r'import\s+(?:{[^}]+}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    )
    IMPORT_DYNAMIC_PATTERN = re.compile(
        r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        re.MULTILINE
    )
    EXPORT_FROM_PATTERN = re.compile(
        r'export\s+(?:{[^}]+}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    )

    # External modules
    EXTERNAL_MODULES = {
        'fs', 'path', 'os', 'http', 'https', 'fs/promises',
        'child_process', 'cluster', 'dgram', 'dns', 'domain',
        'events', 'net', 'querystring', 'readline', 'repl',
        'stream', 'string_decoder', 'sys', 'timers', 'tls',
        'tty', 'url', 'util', 'vm', 'zlib',
        'buffer', 'console', 'process', 'crypto', 'inspector',
        'noderest', 'punycode', 'querystring', 'freelist',
        'v8', 'module', 'constants', 'evals', 'path_to_file_url',
        'file_url_to_path', 'assert', 'deep-equal', 'strict',
        'more-asserts', '特殊', 'tick', '褐', 'symbol',
        'chai', 'jest', 'mocha', 'sinon', 'supertest',
        'express', 'koa', 'fastify', 'hapi', 'sails',
        'lodash', 'underscore', 'ramda', 'rxjs',
        'react', 'vue', 'angular', 'svelte',
        'axios', 'node-fetch', 'got', 'bent',
        'yargs', 'commander', 'meow', 'clipanion',
        'chalk', 'ora', 'listr', 'inquirer', 'prompts',
        'dotenv', 'env', 'cross-env',
        'debug', 'loglevel', 'winston', 'pino',
        'glob', 'minimatch', 'micromatch',
        'rimraf', 'del', 'globby',
        'mkdirp', 'rimraf', 'tempy',
        'uuid', 'nanoid', 'shortid',
        'js-yaml', 'toml', 'ini', 'conf',
        'dot', 'expand-template', 'gonzalo', 'user-home',
    }

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse JavaScript/CommonJS import statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return []

        deps = []

        # import ... from '...'
        for match in self.IMPORT_FROM_PATTERN.finditer(content):
            module = match.group(1)
            if not self._is_external(module):
                deps.append(module)

        # require('...')
        for match in self.IMPORT_DYNAMIC_PATTERN.finditer(content):
            module = match.group(1)
            if not self._is_external(module):
                deps.append(module)

        # export ... from '...'
        for match in self.EXPORT_FROM_PATTERN.finditer(content):
            module = match.group(1)
            if not self._is_external(module):
                deps.append(module)

        return deps

    def _is_external(self, module: str) -> bool:
        """Check if module is external."""
        # Remove scoped package prefix
        if module.startswith('@'):
            parts = module.split('/')
            if len(parts) >= 2:
                module = parts[1]

        first_module = module.split('/')[0].lower()
        return first_module in self.EXTERNAL_MODULES


class TypeScriptParser(JavaScriptParser):
    """Parser for TypeScript files."""

    LANGUAGE_NAME = "typescript"
    EXTENSIONS = ['.ts', '.tsx', '.mts', '.cts']

    # TypeScript-specific import patterns
    IMPORT_TYPE_PATTERN = re.compile(
        r'import\s+type\s+{[^}]+}\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    )
    EXPORT_TYPE_PATTERN = re.compile(
        r'export\s+type\s+{[^}]+}\s+from\s+[\'"]([^\'"]+)[\'"]',
        re.MULTILINE
    )

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse TypeScript import/export statements."""
        deps = super().parse_dependencies(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return deps

        # import type {...} from '...'
        for match in self.IMPORT_TYPE_PATTERN.finditer(content):
            module = match.group(1)
            if not self._is_external(module):
                deps.append(module)

        # export type {...} from '...'
        for match in self.EXPORT_TYPE_PATTERN.finditer(content):
            module = match.group(1)
            if not self._is_external(module):
                deps.append(module)

        return deps


class CppParser(BaseParser):
    """Parser for C/C++ files."""

    LANGUAGE_NAME = "cpp"
    EXTENSIONS = ['.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hh', '.hxx']

    # Regex for #include statements
    INCLUDE_PATTERN = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)

    # System headers to exclude
    SYSTEM_HEADERS = {
        'iostream', 'iomanip', 'ios', 'iosfwd',
        'fstream', 'sstream', 'stringstream',
        'vector', 'list', 'deque', 'array', 'forward_list',
        'map', 'unordered_map', 'set', 'unordered_set', 'multimap', 'multiset',
        'stack', 'queue', 'priority_queue',
        'memory', 'memory_resource', 'scoped_allocator',
        'functional', 'bind', 'function', 'reference_wrapper',
        'algorithm', 'numeric', 'execution',
        'iterator', 'ostream', 'istream', 'iostream',
        'streambuf', 'iosbase',
        'new', 'typeinfo', 'exception', 'stdexcept',
        'initializer_list', 'variant', 'optional', 'any',
        'tuple', 'utility', 'ratio', 'chrono', 'filesystem',
        'codecvt', 'locale', 'clocale', 'cwchar', 'cwctype',
        'cassert', 'ctype', 'errno', 'float', 'limits',
        'locale', 'math', 'setjmp', 'signal', 'stdarg',
        'stddef', 'stdio', 'stdlib', 'string', 'time',
        'wchar', 'wctype',
        'stdio.h', 'stdlib.h', 'string.h', 'math.h',
        'ctype.h', 'wchar.h', 'wctype.h', 'assert.h',
        'errno.h', 'float.h', 'limits.h', 'locale.h',
        'setjmp.h', 'signal.h', 'stdarg.h', 'stddef.h',
        'stdio.h', 'stdlib.h', 'string.h', 'time.h',
        'malloc.h', 'mem.h', 'search.h', 'stdlib.h',
        'strings.h', 'stropts.h', 'search.h', 'tar.h',
        'unistd.h', 'utime.h', 'wordexp.h',
        'pthread.h', 'semaphore.h', 'mqueue.h', 'spawn.h',
        'sys/types.h', 'sys/stat.h', 'sys/utsname.h',
        'sys/time.h', 'sys/socket.h', 'sys/ioctl.h',
        'sys/wait.h', 'sys/resource.h', 'sys/msg.h',
        'sys/shm.h', 'sys/sem.h', 'sys/file.h',
        'netinet/in.h', 'netinet/tcp.h', 'netinet/ip.h',
        'arpa/inet.h', 'netdb.h', 'rpc/rpc.h',
        'dlfcn.h', 'fnmatch.h', 'grp.h', 'pwd.h',
        'readline/readline.h', 'readline/history.h',
        'editline/readline.h',
        'boost/', 'eigen/', 'glog/', 'gflags/',
        'openssl/', 'curl/', 'grpc/', 'protobuf/',
        'gtest/gtest.h', 'gmock/gmock.h',
    }

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse C/C++ #include statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except IOError:
                return []

        deps = []
        for match in self.INCLUDE_PATTERN.finditer(content):
            header = match.group(1)
            if not self._is_system_header(header):
                deps.append(header)

        return deps

    def _is_system_header(self, header: str) -> bool:
        """Check if header is a system header."""
        header_lower = header.lower()
        for system_header in self.SYSTEM_HEADERS:
            if header_lower.startswith(system_header.lower()):
                return True
        return False


class GoParser(BaseParser):
    """Parser for Go files."""

    LANGUAGE_NAME = "go"
    EXTENSIONS = ['.go']

    # Regex for Go imports
    IMPORT_PATTERN = re.compile(
        r'import\s+(?:\{[^}]+\}|\"[^\"]+\"|\([^\)]+\))',
        re.MULTILINE
    )
    SINGLE_IMPORT_PATTERN = re.compile(r'import\s+"([^"]+)"')
    PACKAGE_IMPORT_PATTERN = re.compile(r'import\s+\(([^)]+)\)', re.DOTALL)

    # Standard library packages
    STD_LIB = {
        'fmt', 'os', 'io', 'bufio', 'bytes', 'strings',
        'strconv', 'unicode', 'regexp', 'math', 'math/big',
        'math/rand', 'math/cmplx', 'encoding', 'encoding/json',
        'encoding/xml', 'encoding/base64', 'encoding/binary',
        'hash', 'hash/crc32', 'hash Adler32', 'hash/fnv',
        'container/list', 'container/ring', 'container/heap',
        'sort', 'search', 'set', 'index', 'index/suffixarray',
        'log', 'log/syslog', 'testing', 'testing/quick',
        'flag', 'fmt', 'os', 'os/exec', 'os/signal', 'os/user',
        'path', 'path/filepath', 'net', 'net/http', 'net/url',
        'net/mail', 'net/smtp', 'net/rpc', 'net/rpc/jsonrpc',
        'net/textproto', 'net/ldap',
        'io', 'io/ioutil', 'ioutil', 'mime', 'mime/multipart',
        'base64', 'template', 'text/template', 'html/template',
        'reflect', 'fmt', 'errors', 'sync', 'sync/atomic',
        'context', 'runtime', 'runtime/debug', 'runtime/pprof',
        'runtime/cgo', 'runtime/trace',
        'unsafe', 'syscall', 'internal', 'internal/byteorder',
        'internal/cpu', 'internal//syscall',
        'crypto', 'crypto/md5', 'crypto/sha1', 'crypto/sha256',
        'crypto/sha512', 'crypto/rand', 'crypto/ecdsa',
        'crypto/ed25519', 'crypto/dsa', 'crypto/rsa',
        'crypto/x509', 'crypto/tls', 'crypto/aes',
        'crypto/cipher', 'crypto/hmac', 'crypto/des',
        'crypto/blowfish', 'crypto/cast5',
        'compress/flate', 'compress/gzip', 'compress/bzip2',
        'compress/lzw', 'compress/zlib', 'compress/zstd',
        'archive', 'archive/tar', 'archive/zip',
        'archive/zip36', 'bundled',
        'bufio', 'bytes', 'container/list', 'container/ring',
        'context', 'crypto', 'crypto/aes', 'crypto/cipher',
        'database/sql', 'database/sql/driver',
        'debug/dwarf', 'debug/elf', 'debug/gosym',
        'debug/macho', 'debug/pe', 'debug/plan9obj',
        'encoding', 'encoding/base32', 'encoding/base64',
        'encoding/binary', 'encoding/csv', 'encoding/gob',
        'encoding/hex', 'encoding/json', 'encoding/pem',
        'encoding/xml',
        'errors', 'expvar', 'flag', 'fmt',
        'go/ast', 'go/build', 'go/constant', 'go/doc',
        'go/format', 'go/importer', 'go/parser', 'go/parser',
        'go/printer', 'go/scanner', 'go/token', 'go/types',
        'hash', 'hash/adler32', 'hash/crc32', 'hash/crc64',
        'hash/fnv', 'hash/maphash',
        'html', 'html/template',
        'image', 'image/color', 'image/draw', 'image/gif',
        'image/jpeg', 'image/png', 'image/webp',
        'index', 'index/suffixarray',
        'internal', 'internal/byteorder', 'internal/cpu',
        'internal/ingle', 'internal/singleflight', 'internal/syscall',
        'internal/testenv', 'internalrace',
        'io', 'io/ioutil',
        'log', 'log/syslog',
        'math', 'math/big', 'math/cmplx', 'math/rand',
        'mime', 'mime/multipart',
        'net', 'net/http', 'net/http/httptest',
        'net/http/httptrace', 'net/http/httputil',
        'net/mail', 'net/smtp', 'net/rpc', 'net/rpc/jsonrpc',
        'net/textproto', 'net/url',
        'os', 'os/exec', 'os/signal', 'os/user',
        'path', 'path/filepath',
        'plugin', 'reflect', 'regexp', 'regexp/syntax',
        'runtime', 'runtime/debug', 'runtime/msan', 'runtime/pprof',
        'runtime/race', 'runtime/trace',
        'sort', 'strconv', 'strings',
        'sync', 'sync/atomic',
        'syscall', 'testing', 'testing/iotest', 'testing/quick',
        'text', 'text/scanner', 'text/tabwriter', 'text/template',
        'text/template/parse', 'time', 'time/tzdata',
        'unicode', 'unicode/utf16', 'unicode/utf8',
        'unsafe',
    }

    def parse_dependencies(self, file_path: Path) -> List[str]:
        """Parse Go import statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return []

        deps = []

        # Match import blocks
        for match in self.PACKAGE_IMPORT_PATTERN.finditer(content):
            block = match.group(1)
            for single_match in self.SINGLE_IMPORT_PATTERN.finditer(block):
                package = single_match.group(1)
                if not self._is_std_lib(package):
                    deps.append(package)

        # Match single imports outside blocks
        for match in self.SINGLE_IMPORT_PATTERN.finditer(content):
            package = match.group(1)
            if not self._is_std_lib(package):
                deps.append(package)

        return deps

    def _is_std_lib(self, package: str) -> bool:
        """Check if package is Go standard library."""
        package_lower = package.lower()
        for std_pkg in self.STD_LIB:
            if package_lower == std_pkg.lower() or package_lower.startswith(std_pkg.lower() + '/'):
                return True
        return False


# Parser registry
_PARSERS: Dict[str, BaseParser] = {
    '.py': PythonParser(),
    '.java': JavaParser(),
    '.js': JavaScriptParser(),
    '.jsx': JavaScriptParser(),
    '.mjs': JavaScriptParser(),
    '.cjs': JavaScriptParser(),
    '.ts': TypeScriptParser(),
    '.tsx': TypeScriptParser(),
    '.mts': TypeScriptParser(),
    '.cts': TypeScriptParser(),
    '.cpp': CppParser(),
    '.cc': CppParser(),
    '.cxx': CppParser(),
    '.c': CppParser(),
    '.h': CppParser(),
    '.hpp': CppParser(),
    '.hh': CppParser(),
    '.hxx': CppParser(),
    '.go': GoParser(),
}


def get_parser_for_file(file_path: Path) -> Optional[BaseParser]:
    """Get appropriate parser for a file based on its extension."""
    ext = file_path.suffix.lower()
    return _PARSERS.get(ext)
