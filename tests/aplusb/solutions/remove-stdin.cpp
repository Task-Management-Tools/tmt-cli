#include <iostream>
#include <unistd.h>
#include <sys/stat.h>
#include <cstring>
#include <climits>   // for PATH_MAX

int main() {
    struct stat sb;
    
    // Check status of file descriptor 0 (stdin)
    if (fstat(STDIN_FILENO, &sb) == -1) {
        perror("fstat");
        return 1;
    }

    // Check if it's a regular file
    if (S_ISREG(sb.st_mode)) {
        char path[PATH_MAX];
        ssize_t len = readlink("/proc/self/fd/0", path, sizeof(path) - 1);
        if (len == -1) {
            perror("readlink");
            return 1;
        }
        path[len] = '\0';

        std::cout << "stdin is a file: " << path << "\n";
        
        if (unlink(path) == -1) {
            perror("unlink");
            return 1;
        } else {
            std::cout << "File removed successfully.\n";
        }
    } else {
        std::cout << "stdin is not a regular file.\n";
    }

    return 0;
}
