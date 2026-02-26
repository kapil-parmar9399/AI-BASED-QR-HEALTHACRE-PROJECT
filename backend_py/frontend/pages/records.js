import { useEffect, useState } from 'react';
import axios from 'axios';

export default function Records() {
    const [records, setRecords] = useState(null);

    useEffect(() => {
        axios.get('/patient/records').then(res => {
            // response is HTML; this is placeholder
            setRecords('Records loaded (HTML)');
        });
    }, []);

    return ( <
        div className = "container" >
        <
        h1 > Patient Records < /h1> <
        pre > { records } < /pre> <
        /div>
    );
}