

export type Item = {
  id: string,
  type: string,
  icon: string,
  link: string,
  description?: string,
  };


export type Section = {
  id: string,
  type: string,
  icon: string,
  expanded: boolean,
  children: Array<Item>,
  path?: Array<string>,
};
