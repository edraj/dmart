
<a href="https://github.com/edraj/dmart/releases/latest">
<img src="https://github.com/edraj/dmart/actions/workflows/frontend-checks.yml/badge.svg" > 
</a>

<!--a href="https://github.com/edraj/dmart/releases/latest">
<img alt="Latest release" src="https://img.shields.io/github/v/release/edraj/dmart" />
</a-->

<a href="https://github.com/edraj/dmart/pulse">
<img alt="Last commit" src="https://img.shields.io/github/last-commit/edraj/dmart"/>
</a>

<a href="https://github.com/edraj/dmart/blob/main/LICENSE">
<img alt="License" src="https://img.shields.io/github/license/edraj/dmart" />
</a>

<a href="https://github.com/edraj/dmart/stargazers">
<img alt="Stars" src="https://img.shields.io/github/stars/edraj/dmart" />
</a>

<a href="https://github.com/edraj/dmart/issues">
<img alt="Issues" src="https://img.shields.io/github/issues/edraj/dmart" />
</a>

<a href="https://github.com/edraj/dmart">
<img alt="Repo Size" src="https://img.shields.io/github/repo-size/edraj/dmart" />
</a>


## Skeleton web app (frontend) for DMART



### Installation

The Frontend requires a proper setup of DMART server. 

Currently the code is confirgured to use https://api.dmart.cc
(The configuration option `backend` can be found under src/config.ts)

```bash

git clone https://github.com/edraj/dmart.git
cd dmart/frontend
yarn install


# To run in dev mode : 
yarn dev

# To run in file-server mode (i.e. without Nodejs):
yarn build
caddy run

```


Building tauri binary (Linux AppImage)

```
# Regular build without inspection
yarn tauri build --bundles appimage

# To add inspection (right mouse click -> inspect)
yarn tauri build --bundles appimage --debug

```

