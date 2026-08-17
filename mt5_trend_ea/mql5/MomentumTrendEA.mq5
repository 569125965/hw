#property copyright "Research EA: momentum-gated SuperTrend"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input string InpComment          = "MomentumTrendEA";
input double InpRiskPercent      = 1.0;    // 单笔风险占净值%
input int    InpStPeriod         = 10;
input double InpStMult           = 3.0;
input int    InpAtrPeriod        = 14;
input double InpSlAtr            = 1.0;    // 回测写入：GC=F M5 走步最优
input double InpRR               = 2.0;
input int    InpH1Ema            = 50;
input double InpMinAdx           = 18.0;
input double InpMinScore         = -0.30;  // 回测约 40 分位；过严会把样本打太薄
input int    InpMaxSpreadPoints  = 400;    // 黄金常见点值，按经纪商改
input bool   InpOnePosition      = true;

CTrade trade;

int hAtr = INVALID_HANDLE;
int hAdx = INVALID_HANDLE;
int hEmaH1 = INVALID_HANDLE;

int OnInit()
{
   trade.SetExpertMagicNumber(260817);
   hAtr = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   hAdx = iADX(_Symbol, PERIOD_CURRENT, 14);
   hEmaH1 = iMA(_Symbol, PERIOD_H1, InpH1Ema, 0, MODE_EMA, PRICE_CLOSE);
   if(hAtr == INVALID_HANDLE || hAdx == INVALID_HANDLE || hEmaH1 == INVALID_HANDLE)
      return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hAdx != INVALID_HANDLE) IndicatorRelease(hAdx);
   if(hEmaH1 != INVALID_HANDLE) IndicatorRelease(hEmaH1);
}

void OnTick()
{
   static datetime lastBar = 0;
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(t == lastBar)
      return;
   lastBar = t;

   if(InpOnePosition && PositionSelect(_Symbol))
      return;
   if(!SpreadOk())
      return;

   const int bars = 80;
   if(Bars(_Symbol, PERIOD_CURRENT) < bars + 5)
      return;

   double high[], low[], close[], atr[], adx[], pdi[], mdi[], emaH1[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(atr, true);
   ArraySetAsSeries(adx, true);
   ArraySetAsSeries(pdi, true);
   ArraySetAsSeries(mdi, true);
   ArraySetAsSeries(emaH1, true);

   if(CopyHigh(_Symbol, PERIOD_CURRENT, 0, bars, high) < bars) return;
   if(CopyLow(_Symbol, PERIOD_CURRENT, 0, bars, low) < bars) return;
   if(CopyClose(_Symbol, PERIOD_CURRENT, 0, bars, close) < bars) return;
   if(CopyBuffer(hAtr, 0, 0, bars, atr) < bars) return;
   if(CopyBuffer(hAdx, 0, 0, bars, adx) < bars) return;
   if(CopyBuffer(hAdx, 1, 0, bars, pdi) < bars) return;
   if(CopyBuffer(hAdx, 2, 0, bars, mdi) < bars) return;
   if(CopyBuffer(hEmaH1, 0, 0, 3, emaH1) < 3) return;

   int trend[];
   double stLine[];
   ArrayResize(trend, bars);
   ArrayResize(stLine, bars);
   SuperTrendDir(high, low, close, atr, InpStMult, trend, stLine);

   // Need a trend that has already lived 10+ minutes (3 M5 bars) plus a pullback.
   if(trend[1] != trend[2] || trend[2] != trend[3])
      return;

   int dir = trend[1];
   double h1Close = iClose(_Symbol, PERIOD_H1, 1);
   int h1Dir = (h1Close >= emaH1[1]) ? 1 : -1;
   if(dir != h1Dir)
      return;
   if(adx[1] < InpMinAdx)
      return;

   bool pullback = false;
   if(dir > 0)
      pullback = (low[1] <= stLine[1] + 0.5 * atr[1]) && (close[1] >= stLine[1]);
   else
      pullback = (high[1] >= stLine[1] - 0.5 * atr[1]) && (close[1] <= stLine[1]);
   if(!pullback)
      return;

   double score = MomentumScore(close, high, low, atr, adx, pdi, mdi, dir);
   if(score < InpMinScore)
      return;

   double slDist = InpSlAtr * atr[1];
   if(slDist <= 0)
      return;

   double price = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = (dir > 0) ? price - slDist : price + slDist;
   double tp = (dir > 0) ? price + slDist * InpRR : price - slDist * InpRR;
   double lots = VolumeForRisk(slDist);
   if(lots <= 0)
      return;

   if(dir > 0)
      trade.Buy(lots, _Symbol, price, sl, tp, InpComment);
   else
      trade.Sell(lots, _Symbol, price, sl, tp, InpComment);
}

bool SpreadOk()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return spread > 0 && spread <= InpMaxSpreadPoints;
}

double VolumeForRisk(const double slDist)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk = equity * InpRiskPercent / 100.0;
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tickSize <= 0 || tickValue <= 0 || slDist <= 0)
      return 0;
   double lossPerLot = (slDist / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return 0;
   double lots = MathFloor((risk / lossPerLot) / step) * step;
   lots = MathMax(vmin, MathMin(vmax, lots));
   return lots;
}

void SuperTrendDir(const double &high[], const double &low[], const double &close[],
                   const double &atr[], const double mult, int &trend[], double &st[])
{
   int n = ArraySize(close);
   double up[], dn[];
   ArrayResize(up, n);
   ArrayResize(dn, n);
   ArrayInitialize(trend, 1);
   for(int i = n - 1; i >= 0; --i)
   {
      double src = 0.5 * (high[i] + low[i]);
      up[i] = src - mult * atr[i];
      dn[i] = src + mult * atr[i];
   }
   for(int i = n - 2; i >= 0; --i)
   {
      if(close[i + 1] > up[i + 1])
         up[i] = MathMax(up[i], up[i + 1]);
      if(close[i + 1] < dn[i + 1])
         dn[i] = MathMin(dn[i], dn[i + 1]);
      int prev = trend[i + 1];
      if(prev == -1 && close[i] > dn[i + 1])
         trend[i] = 1;
      else if(prev == 1 && close[i] < up[i + 1])
         trend[i] = -1;
      else
         trend[i] = prev;
      st[i] = (trend[i] == 1) ? up[i] : dn[i];
   }
   st[n - 1] = (trend[n - 1] == 1) ? up[n - 1] : dn[n - 1];
}

double MomentumScore(const double &close[], const double &high[], const double &low[],
                     const double &atr[], const double &adx[], const double &pdi[],
                     const double &mdi[], const int dir)
{
   // Lightweight live approximation of the research composite:
   // signed ROC(6/12), ER(10), ADX slope, DI alignment, extension penalty.
   double roc6 = (close[1] / close[7] - 1.0) * dir;
   double roc12 = (close[1] / close[13] - 1.0) * dir;
   double erNum = MathAbs(close[1] - close[11]);
   double erDen = 0.0;
   for(int i = 1; i <= 10; ++i)
      erDen += MathAbs(close[i] - close[i + 1]);
   double er = (erDen > 0) ? erNum / erDen : 0;
   double adxSlope = adx[1] - adx[7];
   double diAlign = (dir > 0) ? (pdi[1] - mdi[1]) : (mdi[1] - pdi[1]);
   double ext = (dir > 0) ? (close[1] - low[1]) / MathMax(atr[1], 1e-8)
                          : (high[1] - close[1]) / MathMax(atr[1], 1e-8);
   double extPen = -MathMax(ext - 1.8, 0.0);

   // Rough scale to match z-score-ish units without a 200-bar window.
   double score = 0;
   score += roc6 / 0.002;
   score += roc12 / 0.003;
   score += (er - 0.4) / 0.2;
   score += adxSlope / 5.0;
   score += diAlign / 15.0;
   score += extPen;
   return score / 6.0;
}
