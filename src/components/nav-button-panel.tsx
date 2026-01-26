// import Button from '@mui/material/Button'
import ButtonGroup from '@mui/material/ButtonGroup'
import IconButton from '@mui/material/IconButton';
// import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import ArrowLeftIcon from '@mui/icons-material/ArrowLeft';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
// import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FastForwardIcon from '@mui/icons-material/FastForward'
import FastRewindIcon from '@mui/icons-material/FastRewind'

export default function NavButtonPanel({waterlevelIndex, setWaterlevelIndex, maxIndex}: {waterlevelIndex: number, setWaterlevelIndex: (index: number) => void, maxIndex: number}) {
    console.log('NavButtonPanel render')

    function decrementWaterlevelKey(increment=1) {
    if (waterlevelIndex === 0) { 
      console.log('no more waterlevel data')
      return 
    }
    setWaterlevelIndex(waterlevelIndex - increment)
  }
  
  function incrementWaterlevelKey(increment=1) {
    if (waterlevelIndex === maxIndex) { 
      console.log('no more waterlevel data')
      return 
    }
    setWaterlevelIndex(waterlevelIndex + increment)
  }

  function setAbsoluteIndex(index: number) {
    if (index < 0 || index > maxIndex) { 
        console.log('index out of bounds')
        return 
    }
    setWaterlevelIndex(index)
  }

    return (
    <ButtonGroup variant="contained" aria-label="Basic button group">
        <IconButton title="skip to the first record"aria-label="skip to first record" disabled={waterlevelIndex === 0} color="primary" onClick={() => setAbsoluteIndex(0)}>
            <SkipPreviousIcon />
        </IconButton>
        <IconButton aria-label="fast backward" color="primary" onClick={() => decrementWaterlevelKey(12)}>
            <FastRewindIcon />
        </IconButton>
        <IconButton aria-label="previous record" color="primary" onClick={() => decrementWaterlevelKey()}>
            <ArrowLeftIcon fontSize='large'/>
        </IconButton>
        <IconButton aria-label="next record" color="primary" onClick={() => incrementWaterlevelKey()}>
            <ArrowRightIcon fontSize='large'  />
        </IconButton>
        <IconButton color="primary" aria-label="fast forward" onClick={() => incrementWaterlevelKey(12)}>
            <FastForwardIcon />
        </IconButton>
        <IconButton aria-label="skip to last record" disabled={waterlevelIndex === maxIndex} color="primary" onClick={() => setAbsoluteIndex(maxIndex)}>
            <SkipNextIcon />
        </IconButton>
    </ButtonGroup>
  );
}