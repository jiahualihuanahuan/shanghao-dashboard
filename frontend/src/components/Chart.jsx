import React, { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

const COLORS = ['#5aa9ff', '#ffb454', '#7bd88f', '#ff6b81', '#c792ea', '#4dd0e1', '#f6e05e']

export default function Chart({ series, kind = 'line', height = 220, unit = '' }) {
  const el = useRef(null)
  const chart = useRef(null)

  useEffect(() => {
    chart.current = echarts.init(el.current, null, { renderer: 'canvas' })
    const onResize = () => chart.current && chart.current.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.current && chart.current.dispose()
    }
  }, [])

  useEffect(() => {
    if (!chart.current) return
    const names = Object.keys(series || {})
    chart.current.setOption(
      {
        animation: false,
        backgroundColor: 'transparent',
        color: COLORS,
        grid: { left: 52, right: 14, top: names.length > 1 ? 34 : 14, bottom: 26 },
        legend: names.length > 1
          ? { top: 0, textStyle: { color: '#9fb0c6', fontSize: 10 }, data: names.map((n) => shortName(series[n].label, n)) }
          : undefined,
        tooltip: { trigger: 'axis', valueFormatter: (v) => (typeof v === 'number' ? v.toLocaleString() + (unit ? ' ' + unit : '') : v) },
        xAxis: { type: 'time', axisLabel: { color: '#8da0b8', fontSize: 10 }, axisLine: { lineStyle: { color: '#33445c' } } },
        yAxis: {
          type: 'value', scale: true,
          axisLabel: { color: '#8da0b8', fontSize: 10 },
          splitLine: { lineStyle: { color: '#1f2c3f' } },
        },
        series: names.map((n) => ({
          name: shortName(series[n].label, n),
          type: kind === 'bar' ? 'bar' : 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 1.6 },
          data: series[n].points,
        })),
      },
      true,
    )
  }, [series, kind, unit])

  return <div ref={el} style={{ width: '100%', height }} />
}

function shortName(label, id) {
  return (label || id).replace(/\s*\[.*?\]\s*/g, '').slice(0, 28)
}
