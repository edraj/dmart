#!/bin/bash

# Offline deployment

# The following three steps are done only once and the resulting file can be kept under git
yarn config set yarn-offline-mirror /tmp/js-offline
yarn config set yarn-offline-mirror-pruning true
mv ~/.yarnrc ./

rm -rf yarn.lock node_modules
yarn install
# commit and push the resulting yarn.lock and .yarnrc files to the remove server as well
# Sync the js modules
rsync -av /tmp/js-offline/ TARGET_SERVER:/tmp/js-offline

# On the "offline" target computer
yarn install --offline --frozen-lockfile
yarn build
