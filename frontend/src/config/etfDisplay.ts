export type FundRating = '夯' | '顶级' | '人上人' | 'NPC'

interface FundDisplay {
  companyName: string
  order: number
  rating: FundRating | null
}

// Company names are used on the homepage only.
// Order and ratings follow the Nasdaq 100 and S&P 500 ranking articles.
// The Nasdaq technology ETF 159509 has no rating.
export const ETF_DISPLAY: Readonly<Record<string, FundDisplay>> = {
  '159509': { companyName: '景顺长城', order: 1, rating: null },
  '159696': { companyName: '易方达', order: 1, rating: '夯' },
  '513390': { companyName: '博时', order: 2, rating: '夯' },
  '159659': { companyName: '招商', order: 3, rating: '夯' },
  '159660': { companyName: '汇添富', order: 4, rating: '夯' },
  '513870': { companyName: '富国', order: 5, rating: '夯' },
  '159501': { companyName: '嘉实', order: 6, rating: '顶级' },
  '513100': { companyName: '国泰', order: 7, rating: '顶级' },
  '159632': { companyName: '华安', order: 8, rating: '顶级' },
  '513110': { companyName: '华泰柏瑞', order: 9, rating: '顶级' },
  '159941': { companyName: '广发', order: 10, rating: '人上人' },
  '513300': { companyName: '华夏', order: 11, rating: '人上人' },
  '159513': { companyName: '大成', order: 12, rating: 'NPC' },
  '513500': { companyName: '博时', order: 1, rating: '夯' },
  '513650': { companyName: '南方', order: 2, rating: '顶级' },
  '159612': { companyName: '国泰', order: 3, rating: '人上人' },
  '159655': { companyName: '华夏', order: 4, rating: 'NPC' },
}
