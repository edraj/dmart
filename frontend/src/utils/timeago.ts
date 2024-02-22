
function getFormattedDate(date : Date, prefomattedDate? : string, hideYear = false) {
  // const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec' ];
  const day = date.getDate();
  const month = date.getMonth() + 1;  // MONTH_NAMES[date.getMonth()];
  const year = date.getFullYear();
  const hours = date.getHours();
  let minutes : string = `${(date.getMinutes()<10) ? "0": ""}${date.getMinutes()}`;

  if (prefomattedDate) 
    return `${prefomattedDate} @ ${hours}:${minutes}`;
  
  if (hideYear) 
    return `${day}/${month} @ ${hours}:${minutes}`;

  return `${day}/${month}/${year} @ ${hours}:${minutes}`;
}

export function timeAgo(date : Date) {
  const DAY_IN_MS = 86400000; // 24 * 60 * 60 * 1000
  const today = new Date();
  const yesterday  = new Date(today.getTime() - DAY_IN_MS);
  const seconds = Math.round((today.getTime() - date.getTime()) / 1000);
  const minutes = Math.round(seconds / 60);
  const isToday = today.toDateString() === date.toDateString();
  const isYesterday = yesterday.toDateString() === date.toDateString();
  const isThisYear = today.getFullYear() === date.getFullYear();

  if (seconds < 5) {
    return 'Now';
  } else if (seconds < 60) {
    return `${seconds} seconds ago`;
  } else if (seconds < 90) {
    return 'A minute ago';
  } else if (minutes < 60) {
    return `${minutes} minutes ago`;
  } else if (isToday) {
    return getFormattedDate(date, 'Today');
  } else if (isYesterday) {
    return getFormattedDate(date, 'Yesterday');
  } else if (isThisYear) {
    return getFormattedDate(date, undefined, true);
  }

  return getFormattedDate(date);
}
