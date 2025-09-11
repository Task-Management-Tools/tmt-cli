#include <climits> // for PATH_MAX
#include <cstring>
#include <iostream>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

// Conditional includes for platform-specific headers
#if defined(__APPLE__)
#include <sys/fcntl.h>
#elif defined(__linux__)
// no extra headers needed for readlink
#endif

int main() {
  struct stat sb;

  // Check status of file descriptor 0 (stdin)
  if (fstat(STDIN_FILENO, &sb) == -1) {
    perror("fstat");
    return 0;
  }

  // Check if it's a regular file
  if (!S_ISREG(sb.st_mode)) {
    std::cout << "stdin is not a regular file.\n";
    return 0;
  }


  char path[PATH_MAX];

#if defined(__APPLE__)
  // macOS version: Use fcntl with F_GETPATH
  if (fcntl(STDIN_FILENO, F_GETPATH, path) == -1) {
    perror("fcntl F_GETPATH");
    return 0;
  }
#elif defined(__linux__)
  // Linux version: Use readlink on the /proc filesystem
  ssize_t len = readlink("/proc/self/fd/0", path, sizeof(path) - 1);
  if (len == -1) {
    perror("readlink");
    return 0;
  }
  path[len] = '\0';
#else
  std::cerr << "Unsupported operating system.\n";
#endif

  std::cout << "stdin is a file: " << path << "\n";

  if (unlink(path) == -1) {
    perror("unlink");
    return 0;
  }
  std::cout << "File removed successfully.\n";


  return 0;
}
