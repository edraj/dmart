
<a href="https://github.com/edraj/frontend-skeleton/releases/latest">
<img src="https://github.com/edraj/frontend-skeleton/actions/workflows/dmart-checks.yml/badge.svg" > 
</a>

<!--a href="https://github.com/edraj/frontend-skeleton/releases/latest">
<img alt="Latest release" src="https://img.shields.io/github/v/release/edraj/frontend-skeleton" />
</a-->

<a href="https://github.com/edraj/frontend-skeleton/pulse">
<img alt="Last commit" src="https://img.shields.io/github/last-commit/edraj/frontend-skeleton"/>
</a>

<a href="https://github.com/edraj/frontend-skeleton/blob/main/LICENSE">
<img alt="License" src="https://img.shields.io/github/license/edraj/frontend-skeleton" />
</a>

<a href="https://github.com/edraj/frontend-skeleton/stargazers">
<img alt="Stars" src="https://img.shields.io/github/stars/edraj/frontend-skeleton" />
</a>

<a href="https://github.com/edraj/frontend-skeleton/issues">
<img alt="Issues" src="https://img.shields.io/github/issues/edraj/frontend-skeleton" />
</a>

<a href="https://github.com/edraj/frontend-skeleton">
<img alt="Repo Size" src="https://img.shields.io/github/repo-size/edraj/frontend-skeleton" />
</a>


## Skeleton web app (frontend) for DMART



### Installation

The Frontend requires a proper setup of DMART server. 

Currently the code is confirgured to use https://api.dmart.cc
(The configuration option `backend` can be found under src/config.ts)

```bash

git clone https://github.com/edraj/frontend-skeleton.git
cd frontend-skeleton
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

