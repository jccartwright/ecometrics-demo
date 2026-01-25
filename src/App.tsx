import { useState, useEffect, useRef} from 'react'
import { useLoadJSON } from './hooks/useLoadJson'
import * as Plot from "@observablehq/plot"
// import * as d3 from "d3"

import './App.css'


interface Well {
    id: string
    x: number
    min_z: number
    max_z: number
  }

interface Elevation {
    distance_along_profile: number
    elevation: number
}

interface WaterLevelEntry {
  id: string
  x: number
  z: number
}

interface WaterLevel {
  label: string
  values: WaterLevelEntry[]
}

const filePrefixes = ['xs1', 'xs2']

function App() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [filePrefix, setFilePrefix] = useState(filePrefixes[0])
  const [waterlevelIndex, setWaterlevelIndex] = useState(0)
  const [intervalId, setIntervalId] = useState<number>()

  function decrementWaterlevelKey() {
    if (waterlevelIndex === 0) { 
      console.log('no more waterlevel data')
      return 
    }
    setWaterlevelIndex(waterlevelIndex - 12)
  }
  
  function incrementWaterlevelKey() {
    if (waterlevelIndex === waterlevelsData?.length) { 
      console.log('no more waterlevel data')
      return 
    }
    setWaterlevelIndex(waterlevelIndex + 12)
  }

  function startAnimation() {
    if (intervalId) {
      console.log('animation already running')
      return
    }
    console.log('starting animation')
    setIntervalId(setInterval(()=>{setWaterlevelIndex(waterlevelIndex => waterlevelIndex + 1)}, 250))
  }

  function stopAnimation() {
    if (intervalId) {
      console.log('stopping animation')
      clearInterval(intervalId)
      setIntervalId(undefined)
    }
  }

  // expects file in public folder
  const { data:wellsData, loading:wellsLoading, error:wellsError } = useLoadJSON<Well[]>(`${filePrefix}_wells.json`)
  const { data:elevationsData, loading:elevationsLoading, error:elevationsError } = useLoadJSON<Elevation[]>(`${filePrefix}_elevations.json`)
  const { data:waterlevelsData, loading:waterlevelsLoading, error:waterlevelsError } = useLoadJSON<WaterLevel[]>(`${filePrefix}_waterlevels.json`)

  useEffect(() => {
    if (!waterlevelsData) {
      // console.log('waterlevels data not yet loaded')
      return;
    }
    if (!wellsData) {
      // console.log('wells data not yet loaded')
      return;
    }
    if (!elevationsData) {
      // console.log('elevations data not yet loaded')
      return;
    }
    const waterlevelData = waterlevelsData[waterlevelIndex]

    const plot = Plot.plot({
      width: 1500,
      marginLeft: 50,
      grid: true,
      color: {
        legend: true,
      },
      marks: [
        Plot.line(elevationsData, {x: "x", y: "z", stroke: "red"}),
        Plot.line(waterlevelData?.values, {x: "x", y: "z", stroke: "green"}),
        Plot.dot(waterlevelData?.values, { x: "x", y: "z", r: 6, fill: "green", stroke: "green"}),
        Plot.rect(wellsData, {
          x1: (d => d.x - 0.5),
          x2: (d => d.x + 0.5),
          y1: (d => d.min_z),
          y2: (d => d.max_z),
          stroke: "black",
          fillOpacity: 0.1,
          fill: "blue"
        })
      ]
    })
    
    // const plot = Plot.plot({
    //   y: {grid: true},
    //   color: {scheme: "burd"},
    //   marks: [
    //     Plot.ruleY([0]),
    //     Plot.dot(waterlevelData?.values, 
    //       {x: "x", y: "z", stroke: "green", fill: "green", r: 4, title: d => `Well ${d.id}\nWaterlevel: ${d.z} m`})
    //     ]
    // });
    containerRef?.current?.append(plot);

    return () => plot.remove();
  }, [wellsData, elevationsData, waterlevelsData, waterlevelIndex]);

  if (wellsLoading || elevationsLoading || waterlevelsLoading) return <div>Loading data...</div>
  if (wellsError || elevationsError || waterlevelsError) return <div>Error loading data</div>
  if (!(wellsData && elevationsData && waterlevelsData)) return null // no data in files - should not happen

  return (
    <>
    <div ref={containerRef} />

    <p>Profile: {filePrefix}</p>
    <p>{wellsData.length} wells</p>
    <p>{elevationsData.length} survey stations</p>
    <p>{waterlevelsData.length} water level measurements</p>
    <p>Measurement datetime: {waterlevelsData[waterlevelIndex]?.label}</p>
    <div className="card">
      <button onClick={decrementWaterlevelKey}>Previous</button>
      <button onClick={incrementWaterlevelKey}>Next</button>
      <button onClick={startAnimation}>Start</button>
      <button onClick={stopAnimation}>Stop</button>
      <button onClick={() => setFilePrefix(filePrefixes[0])}>Change Profile</button>
    </div>      
    </>
  )
}
export default App