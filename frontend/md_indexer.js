import fs from 'fs';
import path from 'path';

function getMarkdownFiles(dir) {
    let markdownFiles = [];
    const files = fs.readdirSync(dir);

    for (const file of files) {
        const filePath = path.join(dir, file);
        const stats = fs.statSync(filePath);

        if (stats.isDirectory()) {
            markdownFiles = markdownFiles.concat(getMarkdownFiles(filePath));
        } else if (path.extname(file) === '.md') {
            const content = fs.readFileSync(filePath, 'utf-8');
            markdownFiles.push({
                path: filePath,
                content: content,
                filename: file,
            });
        }
    }

    return markdownFiles;
}

const markdownFiles = getMarkdownFiles('./src/routes');

fs.writeFileSync('./src/md_indexer.json', JSON.stringify(markdownFiles, null, 2));
