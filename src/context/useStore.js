import {useContext} from 'react';
import {StoreContext} from './StoreContext.js';

export function useStore(){return useContext(StoreContext);}
