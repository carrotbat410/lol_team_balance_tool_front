export const COMMUNITY_CATEGORIES = [
  { value: "NOTICE", label: "공지사항" },
  { value: "RECRUIT", label: "내전모집" },
  { value: "CLAN_PROMOTION", label: "클랜홍보" },
];

export const WRITABLE_MEMBER_CATEGORIES = ["RECRUIT", "CLAN_PROMOTION"];

export const getCommunityCategoryLabel = (category) =>
  COMMUNITY_CATEGORIES.find((item) => item.value === category)?.label || category;
